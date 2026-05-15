# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import json
from typing import Any

import frappe
from frappe import _
from frappe.exceptions import ValidationError
from frappe.model.document import Document
from frappe.utils import add_days, getdate, today
from frappe.utils.data import get_filter

from banking.exceptions import CurrencyMismatchError


class NoFiltersError(ValidationError):
	pass


def _normalize_filter_rows(raw_filters: list) -> list[list[Any]]:
	normalized: list[list[Any]] = []
	for row in raw_filters:
		if not isinstance(row, list | tuple) or len(row) < 4:
			frappe.throw(_("Invalid filter"))
		doctype = row[0]
		if doctype != "Bank Transaction":
			frappe.throw(_("Invalid filter: only Bank Transaction fields are supported"))
		fd = get_filter(doctype, row)
		normalized.append([fd.doctype, fd.fieldname, fd.operator, fd.value])
	return normalized


def _bank_transaction_stats_filters(
	user_filters: list,
	bank_account: str,
	min_date: str,
) -> list[list[Any]]:
	filters = _normalize_filter_rows(user_filters)
	filters.append(["Bank Transaction", "bank_account", "=", bank_account])
	filters.append(["Bank Transaction", "docstatus", "=", 1])
	filters.append(["Bank Transaction", "date", ">=", min_date])
	return filters


@frappe.whitelist()
def get_bank_transaction_match_stats(
	bank_account: str,
	filters: str | None = None,
	bank_reconciliation_rule: str | None = None,
) -> dict[str, Any]:
	"""Count submitted Bank Transactions matching the rule filters (scoped by bank account).

	Windows use calendar days: last 30 days and last 365 days (\"12 months\"), relative to *today*.
	"""
	if not bank_account:
		frappe.throw(_("Bank Account is required"))

	frappe.has_permission("Bank Transaction", ptype="read", throw=True)

	if bank_reconciliation_rule and frappe.db.exists("Bank Reconciliation Rule", bank_reconciliation_rule):
		rule = frappe.get_doc("Bank Reconciliation Rule", bank_reconciliation_rule)
		if rule.bank_account != bank_account:
			frappe.throw(_("Bank Account does not match this Bank Reconciliation Rule"))

	try:
		user_filters = json.loads(filters or "[]")
	except json.JSONDecodeError:
		frappe.throw(_("Invalid filters"))

	if not isinstance(user_filters, list) or not user_filters:
		frappe.throw(_("Please define at least one filter"))

	as_of = getdate(today())
	# Match UI wording: transactions with *date* on or after (today - 30) / (today - 365).
	min_30 = add_days(as_of, -30)
	min_365 = add_days(as_of, -365)

	return {
		"last_30_days": frappe.db.count(
			"Bank Transaction",
			filters=_bank_transaction_stats_filters(user_filters, bank_account, min_30),
		),
		"last_12_months": frappe.db.count(
			"Bank Transaction",
			filters=_bank_transaction_stats_filters(user_filters, bank_account, min_365),
		),
		"as_of": as_of,
	}


class BankReconciliationRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		bank_account: DF.Link
		disabled: DF.Check
		filters: DF.Code | None
		priority: DF.Int
		target_account: DF.Link

	# end: auto-generated types
	def validate(self):
		self.validate_account_currencies()
		self.validate_filters()

	def validate_account_currencies(self):
		bank_account = frappe.db.get_value("Bank Account", self.bank_account, "account")
		bank_account_currency = frappe.db.get_value("Account", bank_account, "account_currency")
		target_account_currency = frappe.db.get_value("Account", self.target_account, "account_currency")

		if bank_account_currency != target_account_currency:
			frappe.throw(
				_("Bank Account and Target Account need to be in the same currency!"), CurrencyMismatchError
			)

	def validate_filters(self):
		if not self.filters:
			frappe.throw(_("Please define at least one filter!"), NoFiltersError)
		try:
			parsed = json.loads(self.filters)
		except json.JSONDecodeError:
			frappe.throw(_("Invalid filters"), NoFiltersError)
		if not parsed:
			frappe.throw(_("Please define at least one filter!"), NoFiltersError)
