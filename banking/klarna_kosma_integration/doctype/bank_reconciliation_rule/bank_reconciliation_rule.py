# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.exceptions import ValidationError
from frappe.model.document import Document

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
		# self.filters is a code field with json, so it has "[]" when empty
		if not self.filters or len(self.filters) <= 2:
			frappe.throw(_("Please define at least one filter!"), NoFiltersError)
