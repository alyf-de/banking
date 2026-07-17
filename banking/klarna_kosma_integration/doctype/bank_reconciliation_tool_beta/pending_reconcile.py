"""Remember draft vouchers from Edit in Full Page and reconcile them on submit.

Pending state is Redis-backed (frappe.cache) with a 24h TTL; it is lost on cache flush.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

CACHE_PREFIX = "banking:pending_bt_reconcile"
CACHE_TTL_SEC = 60 * 60 * 24  # 1 day


def _cache_key(voucher_type: str, voucher_name: str) -> str:
	return f"{CACHE_PREFIX}:{voucher_type}:{voucher_name}"


def remember_pending_reconcile(voucher_type: str, voucher_name: str, transaction_name: str) -> None:
	frappe.cache().set_value(
		_cache_key(voucher_type, voucher_name),
		{"transaction_name": transaction_name},
		expires_in_sec=CACHE_TTL_SEC,
	)


def clear_pending_reconcile(voucher_type: str, voucher_name: str) -> None:
	frappe.cache().delete_value(_cache_key(voucher_type, voucher_name))


def clear_all_pending_reconciles() -> None:
	"""Drop all pending keys (e.g. test tearDown; Redis is not covered by DB rollback)."""
	frappe.cache().delete_keys(CACHE_PREFIX)


def get_pending_reconcile(voucher_type: str, voucher_name: str) -> dict | None:
	return frappe.cache().get_value(_cache_key(voucher_type, voucher_name))


def _voucher_bank_amount(doc, bank_gl_account: str) -> float:
	"""Bank-side amount of a Create voucher in account currency."""
	if doc.doctype == "Payment Entry":
		return flt(doc.received_amount if doc.payment_type == "Receive" else doc.paid_amount)

	if doc.doctype == "Journal Entry":
		return sum(
			flt(row.debit_in_account_currency) + flt(row.credit_in_account_currency)
			for row in doc.accounts
			if row.account == bank_gl_account
		)

	return 0.0


def _pending_bank_gl_and_unallocated(pending: dict) -> tuple[str, float]:
	transaction = frappe.get_doc("Bank Transaction", pending["transaction_name"])
	bank_gl_account = frappe.db.get_value("Bank Account", transaction.bank_account, "account")
	return bank_gl_account, flt(transaction.unallocated_amount)


def validate_pending_reconcile_amount(doc, method: str | None = None) -> None:
	"""before_submit: Create drafts must not exceed the Bank Transaction unallocated amount."""
	pending = get_pending_reconcile(doc.doctype, doc.name)
	if not pending:
		return

	if not frappe.db.exists("Bank Transaction", pending["transaction_name"]):
		clear_pending_reconcile(doc.doctype, doc.name)
		return

	bank_gl_account, unallocated = _pending_bank_gl_and_unallocated(pending)
	voucher_amount = _voucher_bank_amount(doc, bank_gl_account)

	if voucher_amount <= 0:
		frappe.throw(
			_(
				"Cannot submit {0} {1}: no bank amount found for Bank Account GL {2}. Restore the bank account row before submitting."
			).format(doc.doctype, doc.name, bank_gl_account)
		)

	if voucher_amount > unallocated:
		frappe.throw(
			_(
				"Cannot submit {0} {1}: bank amount {2} is greater than Bank Transaction {3} unallocated amount {4}. Reduce the voucher to {4} or less."
			).format(doc.doctype, doc.name, voucher_amount, pending["transaction_name"], unallocated)
		)


def reconcile_if_pending(doc, method: str | None = None) -> None:
	"""doc_events on_submit for Journal Entry / Payment Entry."""
	pending = get_pending_reconcile(doc.doctype, doc.name)
	if not pending:
		return

	if not frappe.db.exists("Bank Transaction", pending["transaction_name"]):
		clear_pending_reconcile(doc.doctype, doc.name)
		return

	from banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta import (
		reconcile_voucher,
	)

	transaction_name = pending["transaction_name"]
	transaction = frappe.get_doc("Bank Transaction", transaction_name)

	already_linked = any(
		row.payment_document == doc.doctype and row.payment_entry == doc.name
		for row in transaction.payment_entries
	)
	if already_linked:
		clear_pending_reconcile(doc.doctype, doc.name)
		return

	if flt(transaction.unallocated_amount) <= 0:
		# Concurrent reconcile may have consumed the BT between before_submit and on_submit.
		clear_pending_reconcile(doc.doctype, doc.name)
		frappe.log_error(
			title=_("Cannot reconcile {0} {1} with Bank Transaction {2}: no unallocated amount left").format(
				doc.doctype, doc.name, transaction_name
			)
		)
		return

	bank_gl_account = frappe.db.get_value("Bank Account", transaction.bank_account, "account")
	voucher_amount = _voucher_bank_amount(doc, bank_gl_account)
	if voucher_amount <= 0:
		# Leave the cache key so the pending link remains discoverable.
		frappe.log_error(
			title=_("Cannot reconcile {0} {1} with Bank Transaction {2}: no bank amount for GL {3}").format(
				doc.doctype, doc.name, transaction_name, bank_gl_account
			)
		)
		return

	try:
		reconcile_voucher(
			transaction_name,
			voucher_amount,
			doc.doctype,
			doc.name,
		)
	except Exception:
		# Leave the cache key so the pending link remains discoverable after a failed attempt.
		frappe.log_error(
			title=_("Failed to reconcile {0} {1} with Bank Transaction {2}").format(
				doc.doctype, doc.name, transaction_name
			)
		)
		return

	clear_pending_reconcile(doc.doctype, doc.name)


def clear_if_pending(doc, method: str | None = None) -> None:
	"""doc_events on_trash for Journal Entry / Payment Entry."""
	clear_pending_reconcile(doc.doctype, doc.name)
