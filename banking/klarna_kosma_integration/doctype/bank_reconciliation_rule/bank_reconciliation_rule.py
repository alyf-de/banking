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

from banking.exceptions import CurrencyMismatchError, PartyMismatchError

# Same cap as List View (`count_upper_bound`): count at most N rows, show "N-1+" when hit.
COUNT_UPPER_BOUND = 1001

PARTY_ACCOUNT_TYPES = ("Receivable", "Payable")


class NoFiltersError(ValidationError):
	pass


def get_party_account_type(account: str) -> str | None:
	"""Return the account type if Journal Entry rows on `account` require a party."""
	account_type = frappe.get_cached_value("Account", account, "account_type")
	return account_type if account_type in PARTY_ACCOUNT_TYPES else None


def party_type_matches_account_type(party_type: str, account_type: str) -> bool:
	# Employees can be both payable and receivable, same exception as ERPNext makes.
	if party_type == "Employee":
		return True

	return frappe.get_cached_value("Party Type", party_type, "account_type") == account_type


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
	normalized_filters: list,
	bank_account: str,
	min_date: str,
) -> list[list[Any]]:
	filters = list(normalized_filters)
	filters.extend(
		[
			["Bank Transaction", "bank_account", "=", bank_account],
			["Bank Transaction", "docstatus", "=", 1],
			["Bank Transaction", "date", ">=", min_date],
		]
	)
	return filters


def _approx_bank_transaction_count(filters: list) -> int:
	"""Fast capped count, same approach as List View (LIMIT then count rows)."""
	return len(
		frappe.get_list(
			"Bank Transaction",
			filters=filters,
			limit_page_length=COUNT_UPPER_BOUND,
			order_by=None,
			pluck="name",
		)
	)


@frappe.whitelist()
def get_bank_transaction_match_stats(
	bank_account: str,
	filters: str | None = None,
	bank_reconciliation_rule: str | None = None,
) -> dict[str, Any]:
	"""Approximate count of submitted Bank Transactions matching the rule filters.

	Uses a capped count (like List View) so large tables stay fast.
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

	normalized_filters = _normalize_filter_rows(user_filters)
	as_of = getdate(today())
	# Match UI wording: transactions with *date* on or after (today - 30) / (today - 365).
	min_30 = add_days(as_of, -30)
	min_365 = add_days(as_of, -365)

	return {
		"last_30_days": _approx_bank_transaction_count(
			_bank_transaction_stats_filters(normalized_filters, bank_account, min_30)
		),
		"last_12_months": _approx_bank_transaction_count(
			_bank_transaction_stats_filters(normalized_filters, bank_account, min_365)
		),
		"as_of": as_of,
		"count_upper_bound": COUNT_UPPER_BOUND,
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
		self.validate_target_account_party()

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

	def validate_target_account_party(self):
		"""Receivable and Payable target accounts need a party on the Journal Entry.

		The party is copied from the matched Bank Transaction, so the rule has to
		restrict itself to transactions with a compatible party type.
		"""
		account_type = get_party_account_type(self.target_account)
		if not account_type:
			return

		party_type = self.get_filter_value("party_type")
		if not party_type:
			frappe.throw(
				_(
					"{0} is a {1} account, so the automatic Journal Entry needs a party. "
					"Please add a {2} filter to restrict this rule to transactions with a party."
				).format(frappe.bold(self.target_account), _(account_type), frappe.bold(_("Party Type"))),
				PartyMismatchError,
			)

		if not party_type_matches_account_type(party_type, account_type):
			frappe.throw(
				_("Party type {0} cannot be booked against the {1} account {2}.").format(
					frappe.bold(_(party_type)), _(account_type), frappe.bold(self.target_account)
				),
				PartyMismatchError,
			)

	def get_filter_value(self, fieldname: str) -> str | None:
		"""Return the value the rule pins `fieldname` to, if it uses an equality filter."""
		for row in json.loads(self.filters):
			if row[1] == fieldname and row[2] == "=":
				return row[3]

		return None
