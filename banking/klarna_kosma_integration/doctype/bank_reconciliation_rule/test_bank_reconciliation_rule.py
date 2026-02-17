# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError
from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	NoFiltersError,
)

TEST_COMPANY = "Bolt Trades"


def create_currency_account(currency: str, parent_account: str, account_name: str):
	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.account_currency = currency
	acc.parent_account = parent_account
	acc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return acc


def create_bank_account(account: str):
	ba = frappe.new_doc("Bank Account")
	ba.account_name = "_Test_B_Account"
	ba.account = account
	ba.bank = "_Test_Bank"
	ba.is_company_account = 1
	ba.insert(ignore_permissions=True, ignore_links=True)
	return ba


class TestBankReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		# these should be cleaned up by the DB rollback of FrappeTestCase
		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
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
