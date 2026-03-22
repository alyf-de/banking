# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.testing_utils import (
	create_bank_account,
	create_currency_account,
	get_bank_parent_account,
	set_automatic_bank_fee_entries,
)


class TestBankAccount(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_automatic_bank_fee_entries(False)

		parent_account = get_bank_parent_account()
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
		set_automatic_bank_fee_entries(False)

	def tearDown(self):
		set_automatic_bank_fee_entries(False)
		super().tearDown()

	def test_currency_mismatch_rejected(self):
		"""Bank and fee accounts must use the same currency."""
		with self.assertRaises(frappe.ValidationError):
			create_bank_account(self.account_eur.name, bank_fee_account=self.account_usd.name)

	def test_requires_fee_account_when_enabled(self):
		"""Company bank accounts cannot be created or saved without a fee account."""
		set_automatic_bank_fee_entries(True)

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
