# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.test_bank_reconciliation_tool_beta import (
	create_bank,
)
from banking.testing_utils import (
	create_bank_account,
	create_currency_account,
	create_mode_of_payment,
	get_bank_parent_account,
	set_automatic_bank_fee_entries,
)


class TestBankAccount(IntegrationTestCase):
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

	def test_default_mode_of_payment_must_book_to_account(self):
		"""Changing the account must not keep a Default Mode of Payment of the old account."""
		mode = create_mode_of_payment("_Test Bank Account Transfer", self.account_eur.name)

		bank_account = frappe.get_doc("Bank Account", self.bank_account_with_fee.name)
		bank_account.flags.ignore_links = True  # the test Bank does not exist
		bank_account.default_mode_of_payment = mode
		bank_account.save()

		bank_account.account = self.account_fee.name
		with self.assertRaises(frappe.ValidationError):
			bank_account.save()

	def test_german_iban_must_match_bank_bic(self):
		"""A Bank with the BIC of another branch must not be linked to a German IBAN."""
		create_bank("_Test Other Branch Bank", swift_number="DEUTDEFF")
		create_bank("_Test Same Branch Bank", swift_number="BELADEBE")

		def new_bank_account(bank: str):
			return frappe.new_doc(
				"Bank Account",
				account_name=frappe.generate_hash(length=8),
				bank=bank,
				iban="DE02100500000054540402",
			)

		with self.assertRaisesRegex(frappe.ValidationError, "BELADEBEXXX"):
			new_bank_account("_Test Other Branch Bank").insert()

		new_bank_account("_Test Same Branch Bank").insert()

	def test_austrian_and_swiss_iban_must_match_bank_bic(self):
		create_bank("_Test Other Branch Bank", swift_number="DEUTDEFF")
		create_bank("_Test Austrian Bank", swift_number="RLNWATWW")  # without the default "XXX"
		create_bank("_Test Swiss Bank", swift_number="CRESCHZZ80A")

		def new_bank_account(bank: str, iban: str):
			return frappe.new_doc(
				"Bank Account",
				account_name=frappe.generate_hash(length=8),
				bank=bank,
				iban=iban,
			)

		for iban, iban_bic, matching_bank in (
			("AT483200000012345864", "RLNWATWWXXX", "_Test Austrian Bank"),
			("CH5604835012345678009", "CRESCHZZ80A", "_Test Swiss Bank"),
		):
			with self.assertRaisesRegex(frappe.ValidationError, iban_bic):
				new_bank_account("_Test Other Branch Bank", iban).insert()

			new_bank_account(matching_bank, iban).insert()
