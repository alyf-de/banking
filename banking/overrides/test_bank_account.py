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


def create_bank_account(
	account: str, bank_fee_account: str | None = None, account_name: str = "_Test_B_Account"
):
	ba = frappe.new_doc("Bank Account")
	ba.account_name = account_name
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
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		cls.account_eur = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.account_usd = create_currency_account("USD", parent_account, "_Test_Account_USD")
		cls.account_fee = create_currency_account("EUR", parent_account, "_Test_Account_EUR_Fee")
		cls.bank_account_with_fee = create_bank_account(
			cls.account_eur.name,
			bank_fee_account=cls.account_fee.name,
			account_name="_Test_B_Account_With_Fee",
		)

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)

	def tearDown(self):
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)
		super().tearDown()

	def test_currency_mismatch_rejected(self):
		"""Bank and fee accounts must use the same currency."""
		with self.assertRaises(frappe.ValidationError):
			create_bank_account(self.account_eur.name, bank_fee_account=self.account_usd.name)

	def test_requires_fee_account_when_enabled(self):
		"""Company bank accounts cannot be created or saved without a fee account."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		with self.assertRaises(frappe.ValidationError):
			create_bank_account(self.account_eur.name, account_name="_Test_B_Account_Without_Fee")

		bank_account = frappe.get_doc("Bank Account", self.bank_account_with_fee.name)
		bank_account.bank_fee_account = None

		with self.assertRaises(frappe.ValidationError):
			bank_account.save()

		self.assertEqual(
			frappe.db.get_value("Bank Account", self.bank_account_with_fee.name, "bank_fee_account"),
			self.account_fee.name,
		)
