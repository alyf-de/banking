# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import json
from typing import cast

import frappe
from frappe import _
from frappe.exceptions import ValidationError
from frappe.model.document import Document
from frappe.utils import cint

from banking.exceptions import CurrencyMismatchError


class NoFiltersError(ValidationError):
	pass


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
		if not self.filters or not json.loads(self.filters):
			frappe.throw(_("Please define at least one filter!"), NoFiltersError)


@frappe.whitelist()
def get_bank_accounts_with_rules() -> list[str]:
	"""Bank accounts that have at least one non-cancelled reconciliation rule."""
	if not frappe.has_permission("Bank Reconciliation Rule", "read"):
		frappe.throw(_("Not permitted to read the bank reconciliation rules"), frappe.PermissionError)

	return frappe.get_all(
		"Bank Reconciliation Rule",
		filters={"docstatus": ("!=", 2)},
		pluck="bank_account",
		group_by="bank_account",
		order_by="bank_account asc",
	)


@frappe.whitelist()
def get_rules_for_reorder(bank_account: str | None = None) -> list[dict]:
	"""Load non-cancelled rules for a bank account (list order = current evaluation order)."""
	if not bank_account:
		frappe.throw(_("Please set a Bank Account"))
	if not frappe.has_permission("Bank Reconciliation Rule", "read"):
		frappe.throw(_("Not permitted to read the bank reconciliation rules"), frappe.PermissionError)

	rules = frappe.get_all(
		"Bank Reconciliation Rule",
		filters={"bank_account": bank_account, "docstatus": ("!=", 2)},
		fields=["name", "target_account", "priority", "docstatus", "disabled"],
		order_by="priority desc, creation asc",
	)
	return list(rules)


@frappe.whitelist()
def reorder_bank_reconciliation_rule_priorities(
	bank_account: str | None = None, ordered_names: str | list | None = None
) -> None:
	"""
	Persist **priority** from a full drag-and-drop order: first row = highest priority
	(must match `order_by` in **Bank Transaction** automatic rules: `priority desc`).
	Values are **10, 20, 30, …** so users can set intermediate priorities (e.g. 15) without
	running the dialog again.
	"""
	if not bank_account:
		frappe.throw(_("Please set a Bank Account"))
	if not frappe.has_permission("Bank Reconciliation Rule", "write"):
		frappe.throw(_("Not permitted to edit the bank reconciliation rules"), frappe.PermissionError)

	raw = frappe.parse_json(ordered_names) if isinstance(ordered_names, str) else ordered_names
	if not raw:
		frappe.throw(_("Please add at least one rule to the list"))
	if not isinstance(raw, list | tuple) or not all(isinstance(n, str) for n in raw):
		frappe.throw(_("Invalid rule order"))
	names = cast("list[str] | tuple[str, ...]", raw)
	ordered: list[str] = [str(n) for n in names]
	if len(ordered) != len(set(ordered)):
		frappe.throw(_("Each rule may only appear once"))

	expected = set(
		frappe.get_all(
			"Bank Reconciliation Rule",
			filters={"bank_account": bank_account, "docstatus": ("!=", 2)},
			pluck="name",
		)
	)
	if set(ordered) != expected:
		frappe.throw(
			_("The order must include every rule for this bank account. Reload the dialog and try again.")
		)

	n = len(ordered)
	for name in ordered:
		if not frappe.has_permission("Bank Reconciliation Rule", "write", name):
			frappe.throw(_("Not permitted to update {0}.").format(name), frappe.PermissionError)

	# Stagger so we do not hold duplicate priorities while renumbering submitted rules
	for i, name in enumerate(ordered):
		frappe.db.set_value(
			"Bank Reconciliation Rule", name, "priority", 1_000_000 + i, update_modified=False
		)

	# 10, 20, 30, … so manually inserted rules can use intermediate priorities without renumbering
	step = 10
	for idx, name in enumerate(ordered):
		priority = cint(n - idx) * step
		frappe.db.set_value("Bank Reconciliation Rule", name, "priority", priority)
