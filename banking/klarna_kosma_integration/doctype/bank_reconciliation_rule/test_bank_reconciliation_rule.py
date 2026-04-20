# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError
from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	NoFiltersError,
)
from banking.testing_utils import create_bank_account, create_currency_account

test_dependencies = ["Company", "Account"]


class TestBankReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": "_Test Company"})
		bank_account = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.target_account = create_currency_account("USD", parent_account, "_Test_Account_USD")
		cls.ba = create_bank_account(bank_account.name)

	def test_validate_account_currencies(self):
		brr_doc = frappe.new_doc("Bank Reconciliation Rule")
		brr_doc.bank_account = self.ba.name
		brr_doc.target_account = self.target_account.name

		with self.assertRaises(CurrencyMismatchError):
			brr_doc.validate_account_currencies()

	def test_validate_filters(self):
		brr_doc = frappe.new_doc("Bank Reconciliation Rule")
		brr_doc.filters = None
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()

		brr_doc.filters = "[]"
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()
