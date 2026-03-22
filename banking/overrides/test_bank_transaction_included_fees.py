# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from erpnext.accounts.doctype.account.test_account import create_account
from frappe.tests.utils import FrappeTestCase

TEST_COMPANY = "Bolt Trades"


def get_bank_parent_account(company: str) -> str:
	return frappe.db.get_value("Account", {"account_type": "Bank", "is_group": 1, "company": company})


def create_currency_account(currency: str, parent_account: str, account_name: str):
	account = create_account(
		account_name=account_name,
		account_type="Bank",
		parent_account=parent_account,
		company=TEST_COMPANY,
		account_currency=currency,
	)
	return frappe.get_doc("Account", account)


def create_bank_account(
	account: str, bank_fee_account: str | None = None, account_name: str = "_Test_B_Account"
):
	ba = frappe.new_doc("Bank Account")
	ba.account_name = account_name
	ba.account = account
	ba.bank = "_Test_Bank"
	ba.company = TEST_COMPANY
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

		parent_account = get_bank_parent_account(TEST_COMPANY)
		cls.account_main = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.account_main_without_fee = create_currency_account(
			"EUR", parent_account, "_Test_Account_EUR_No_Fee"
		)
		cls.account_fee = create_currency_account("EUR", parent_account, "_Test_Account_EUR_Fee")
		cls.bank_account = create_bank_account(cls.account_main.name, bank_fee_account=cls.account_fee.name)
		cls.bank_account_without_fee = create_bank_account(
			cls.account_main_without_fee.name,
			account_name="_Test_B_Account_No_Fee",
		)

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

	def test_submit_without_fee_account_when_automatic_fee_entries_are_disabled(self):
		"""Ensure a Bank Transaction can be submitted without a bank fee account
		when automatic bank fee journal entries are disabled, and assert that
		no linked fee Journal Entry is created."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)

		bt = create_bank_transaction(
			bank_account=self.bank_account_without_fee.name,
			withdrawal=10.0,
			included_fee=1.0,
			date="2025-01-01",
			currency="EUR",
			description="Bank fee should not create a Journal Entry when disabled",
		)

		bt.submit()
		bt.reload()

		self.assertEqual(bt.docstatus, 1)
		self.assertEqual(bt.status, "Unreconciled")
		self.assertFalse(bt.payment_entries)
		self.assertFalse(
			frappe.db.exists(
				"Journal Entry Account",
				{
					"reference_type": "Bank Transaction",
					"reference_name": bt.name,
				},
			)
		)

	def test_submit_creates_and_reconciles_fee_journal_entry_for_withdrawal(self):
		"""Submitting a withdrawal with an included fee must create and reconcile the fee JE."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		bt = create_bank_transaction(
			bank_account=self.bank_account.name,
			withdrawal=5.0,
			included_fee=1.0,
			date=frappe.utils.nowdate(),
			currency="EUR",
			description="Withdrawal with included bank fee",
		)

		bt.submit()
		bt.reload()

		self.assertEqual(bt.docstatus, 1)
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].payment_document, "Journal Entry")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 1.0)
		self.assertEqual(bt.allocated_amount, 1.0)
		self.assertEqual(bt.unallocated_amount, 4.0)

		je = frappe.get_doc("Journal Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(je.docstatus, 1)
		self.assertEqual(je.voucher_type, "Bank Entry")
		self.assertTrue(je.is_system_generated)
		self.assertEqual(je.cheque_no, bt.name)
		self.assertEqual(str(frappe.db.get_value("Journal Entry", je.name, "clearance_date")), str(bt.date))
		self.assertTrue(
			frappe.db.exists(
				"Journal Entry Account",
				{
					"parent": je.name,
					"reference_type": "Bank Transaction",
					"reference_name": bt.name,
				},
			)
		)

		accounts = {row.account: row for row in je.accounts}
		self.assertEqual(accounts[self.account_main.name].credit_in_account_currency, 1.0)
		self.assertEqual(accounts[self.account_fee.name].debit_in_account_currency, 1.0)

	@patch(
		"banking.overrides.bank_transaction.create_automatic_journal_entry",
		return_value="ACC-JV-TEST-FEE",
	)
	def test_create_je_bank_fees_preserves_existing_allocations(self, mock_create_automatic_journal_entry):
		from banking.overrides.bank_transaction import create_je_bank_fees

		bt = create_bank_transaction(
			insert=False,
			bank_account=self.bank_account.name,
			withdrawal=10.0,
			included_fee=1.0,
			date="2025-01-01",
		)
		bt.append(
			"payment_entries",
			{
				"payment_document": "Payment Entry",
				"payment_entry": "ACC-PE-EXISTING",
				"allocated_amount": 3.0,
			},
		)
		bt.allocated_amount = 0.0
		bt.unallocated_amount = 10.0

		create_je_bank_fees(
			bt,
			cost_center=frappe.get_cached_value("Company", TEST_COMPANY, "cost_center"),
			date="2025-01-01",
			account=self.account_main.name,
			debit=0.0,
			credit=10.0,
		)

		mock_create_automatic_journal_entry.assert_called_once()
		self.assertEqual(len(bt.payment_entries), 2)
		self.assertEqual(bt.payment_entries[-1].payment_document, "Journal Entry")
		self.assertEqual(bt.payment_entries[-1].payment_entry, "ACC-JV-TEST-FEE")
		self.assertEqual(bt.payment_entries[-1].allocated_amount, 1.0)
		self.assertEqual(bt.allocated_amount, 4.0)
		self.assertEqual(bt.unallocated_amount, 6.0)

	def test_submit_creates_fee_journal_entry_for_deposit(self):
		"""Submitting a deposit with an included fee must create a cleared fee JE without allocation."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		bt = create_bank_transaction(
			bank_account=self.bank_account.name,
			deposit=5.0,
			included_fee=1.0,
			date=frappe.utils.nowdate(),
			currency="EUR",
			description="Deposit with included bank fee",
		)

		bt.submit()
		bt.reload()

		self.assertEqual(bt.docstatus, 1)
		self.assertEqual(bt.status, "Unreconciled")
		self.assertFalse(bt.payment_entries)
		self.assertEqual(bt.allocated_amount, 0.0)
		self.assertEqual(bt.unallocated_amount, 5.0)

		journal_entries = frappe.get_all(
			"Journal Entry Account",
			filters={
				"reference_type": "Bank Transaction",
				"reference_name": bt.name,
			},
			pluck="parent",
		)
		self.assertEqual(len(journal_entries), 1)

		je = frappe.get_doc("Journal Entry", journal_entries[0])
		self.assertEqual(je.docstatus, 1)
		self.assertEqual(je.voucher_type, "Bank Entry")
		self.assertTrue(je.is_system_generated)
		self.assertEqual(je.cheque_no, bt.name)
		self.assertEqual(str(frappe.db.get_value("Journal Entry", je.name, "clearance_date")), str(bt.date))
		self.assertTrue(
			frappe.db.exists(
				"Journal Entry Account",
				{
					"parent": je.name,
					"reference_type": "Bank Transaction",
					"reference_name": bt.name,
				},
			)
		)

		accounts = {row.account: row for row in je.accounts}
		self.assertEqual(accounts[self.account_main.name].credit_in_account_currency, 1.0)
		self.assertEqual(accounts[self.account_fee.name].debit_in_account_currency, 1.0)

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
