# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_COMPANY = "Bolt Trades"


def create_currency_account(currency: str, parent_account: str, account_name: str):
	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.account_currency = currency
	acc.parent_account = parent_account
	acc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return acc


def create_bank_account(account: str, bank_fee_account: str | None = None):
	ba = frappe.new_doc("Bank Account")
	ba.account_name = "_Test_B_Account"
	ba.account = account
	ba.bank = "_Test_Bank"
	ba.is_company_account = 1
	if bank_fee_account:
		ba.bank_fee_account = bank_fee_account
	ba.insert(ignore_permissions=True, ignore_links=True)
	return ba


class TestBankAccount(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		cls.account_eur = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.account_usd = create_currency_account("USD", parent_account, "_Test_Account_USD")

	def test_validate_account_currencies(self):
		with self.assertRaises(frappe.ValidationError):
			create_bank_account(self.account_eur.name, bank_fee_account=self.account_usd.name)
