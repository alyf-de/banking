# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from unittest.mock import patch

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


def create_bank_transaction(insert=True, **values):
	doc = frappe.new_doc("Bank Transaction")
	doc.company = TEST_COMPANY
	doc.update(values)
	if insert:
		doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return doc


class TestIncludedBankFees(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		cls.account_main = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.account_fee = create_currency_account("EUR", parent_account, "_Test_Account_EUR_Fee")
		cls.bank_account = create_bank_account(cls.account_main.name, bank_fee_account=cls.account_fee.name)

	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_before_submit(self, mock_create_bank_fees):
		from banking.overrides.bank_transaction import before_submit

		bt = create_bank_transaction(insert=False)

		with self.assertRaises(frappe.ValidationError):
			before_submit(bt, None)

		bt.bank_account = self.bank_account.name
		bt.deposit = -1.0
		with self.assertRaises(frappe.ValidationError):
			before_submit(bt, None)

		bt.deposit = 0.0
		bt.withdrawal = -1.0
		with self.assertRaises(frappe.ValidationError):
			before_submit(bt, None)

		bt.withdrawal = 1.0
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)
		before_submit(bt, None)
		mock_create_bank_fees.assert_called_once()

	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_before_submit_with_disabled_automatic_fee_entries(self, mock_create_bank_fees):
		from banking.overrides.bank_transaction import before_submit

		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)
		bt = create_bank_transaction(
			insert=False,
			bank_account=self.bank_account.name,
			withdrawal=10.0,
			included_fee=1.0,
			date="2025-01-01",
		)

		before_submit(bt, None)

		mock_create_bank_fees.assert_not_called()

	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_before_submit_rejects_fee_larger_than_withdrawal(self, mock_create_bank_fees):
		from banking.overrides.bank_transaction import before_submit

		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)
		bt = create_bank_transaction(
			insert=False,
			bank_account=self.bank_account.name,
			withdrawal=1.0,
			included_fee=2.0,
			date="2025-01-01",
		)

		with self.assertRaises(frappe.ValidationError):
			before_submit(bt, None)

		mock_create_bank_fees.assert_not_called()

	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_before_submit_allows_missing_deposit_for_withdrawal_with_fee(self, mock_create_bank_fees):
		from banking.overrides.bank_transaction import before_submit

		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)
		bt = create_bank_transaction(
			insert=False,
			bank_account=self.bank_account.name,
			withdrawal=2.0,
			included_fee=1.0,
			date="2025-01-01",
		)

		before_submit(bt, None)

		mock_create_bank_fees.assert_called_once()

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_bank_fees_withdrawal(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_bank_fees

		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		bt = create_bank_transaction(withdrawal=5.0, included_fee=1.0, bank_account=self.bank_account.name)
		cost_center = frappe.get_cached_value("Company", bt.company, "cost_center")

		create_je_bank_fees(bt, cost_center, date, self.account_main.name, 0, bt.withdrawal)

		mock_create_je.assert_called_once_with(
			company=bt.company,
			bank_account=bt.bank_account,
			bank_transaction=bt.name,
			cost_center=cost_center,
			date=date,
			account=self.account_main.name,
			target_account=self.account_fee.name,
			debit=0,
			credit=1.0,
		)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 1.0)
		self.assertEqual(bt.allocated_amount, 1.0)
		self.assertEqual(bt.unallocated_amount, 4.0)
		self.assertEqual(bt.status, "Pending")

		bt.withdrawal = 1.0
		create_je_bank_fees(bt, cost_center, date, self.account_main.name, 0, bt.withdrawal)
		self.assertEqual(bt.allocated_amount, 1.0)
		self.assertEqual(bt.unallocated_amount, 0.0)
		self.assertEqual(bt.status, "Reconciled")

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_bank_fees_deposit(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_bank_fees

		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		bt = create_bank_transaction(deposit=5.0, included_fee=1.0, bank_account=self.bank_account.name)
		cost_center = frappe.get_cached_value("Company", bt.company, "cost_center")

		create_je_bank_fees(bt, cost_center, date, self.account_main.name, bt.deposit, 0)

		mock_create_je.assert_called_once_with(
			company=bt.company,
			bank_account=bt.bank_account,
			bank_transaction=bt.name,
			cost_center=cost_center,
			date=date,
			account=self.account_main.name,
			target_account=self.account_fee.name,
			debit=0,
			credit=1.0,
		)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 0.0)
		self.assertEqual(bt.allocated_amount, 0.0)
		self.assertEqual(bt.unallocated_amount, 5.0)
		self.assertEqual(bt.status, "Pending")
