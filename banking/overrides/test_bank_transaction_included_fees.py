# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from banking.testing_utils import (
	create_bank_account,
	create_bank_transaction,
	create_currency_account,
	get_bank_parent_account,
	make_bank_transaction,
	set_automatic_bank_fee_entries,
)


class TestIncludedBankFees(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		parent_account = get_bank_parent_account()
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

		bt = make_bank_transaction()

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
		set_automatic_bank_fee_entries(True)
		before_submit(bt, None)
		mock_create_bank_fees.assert_called_once()

	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_before_submit_skips_fee_entries_when_disabled(self, mock_create_bank_fees):
		from banking.overrides.bank_transaction import before_submit

		set_automatic_bank_fee_entries(False)
		bt = make_bank_transaction(
			bank_account=self.bank_account.name,
			withdrawal=10.0,
			included_fee=1.0,
			date="2025-01-01",
		)

		before_submit(bt, None)

		mock_create_bank_fees.assert_not_called()

	def test_submit_without_fee_account_when_disabled(self):
		"""Ensure a Bank Transaction can be submitted without a bank fee account
		when automatic bank fee journal entries are disabled, and assert that
		no linked fee Journal Entry is created."""
		set_automatic_bank_fee_entries(False)

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

	def test_withdrawal_creates_reconciled_fee_journal_entry(self):
		"""Submitting a withdrawal with an included fee must create and reconcile the fee JE."""
		set_automatic_bank_fee_entries(True)

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

	def test_cancel_transaction_cancels_fee_journal_entry(self):
		set_automatic_bank_fee_entries(True)

		bt = create_bank_transaction(
			bank_account=self.bank_account.name,
			withdrawal=5.0,
			included_fee=1.0,
			date=frappe.utils.nowdate(),
			currency="EUR",
			description="Withdrawal fee Journal Entry should cancel with transaction",
		)
		bt.submit()
		bt.reload()
		je = frappe.get_doc("Journal Entry", bt.payment_entries[0].payment_entry)

		bt.cancel()
		je.reload()

		self.assertEqual(bt.docstatus, 2)
		self.assertEqual(je.docstatus, 2)

	@patch(
		"banking.overrides.bank_transaction.create_automatic_journal_entry",
		return_value="ACC-JV-TEST-FEE",
	)
	def test_fee_journal_entry_preserves_allocations(self, mock_create_automatic_journal_entry):
		from banking.overrides.bank_transaction import create_je_bank_fees

		bt = make_bank_transaction(
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
			cost_center=frappe.get_cached_value("Company", "_Test Company", "cost_center"),
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

	def test_deposit_skips_fee_journal_entry(self):
		"""Submitting a deposit with an included fee must NOT create a fee JE.

		The fee is deferred to reconciliation, where the correct counter-account
		(e.g. receivable) is known.
		"""
		set_automatic_bank_fee_entries(True)

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

		self.assertFalse(
			frappe.db.exists(
				"Journal Entry Account",
				{
					"reference_type": "Bank Transaction",
					"reference_name": bt.name,
				},
			)
		)

	@patch("banking.overrides.bank_transaction.frappe.log_error")
	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_zero_amount_included_fee_logs_warning(self, mock_create_bank_fees, mock_log_error):
		set_automatic_bank_fee_entries(True)

		bt = create_bank_transaction(
			bank_account=self.bank_account.name,
			deposit=0.004,
			withdrawal=0.0,
			included_fee=1.0,
			date=frappe.utils.nowdate(),
			currency="EUR",
			description="Zero-amount transaction with included bank fee",
		)

		bt.submit()

		mock_create_bank_fees.assert_not_called()
		mock_log_error.assert_called_once()
		self.assertEqual(mock_log_error.call_args.kwargs["reference_doctype"], "Bank Transaction")
		self.assertEqual(mock_log_error.call_args.kwargs["reference_name"], bt.name)

	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_rejects_fee_larger_than_withdrawal(self, mock_create_bank_fees):
		from banking.overrides.bank_transaction import before_submit

		set_automatic_bank_fee_entries(True)
		bt = make_bank_transaction(
			bank_account=self.bank_account.name,
			withdrawal=1.0,
			included_fee=2.0,
			date="2025-01-01",
		)

		with self.assertRaises(frappe.ValidationError):
			before_submit(bt, None)

		mock_create_bank_fees.assert_not_called()

	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_withdrawal_fee_allows_missing_deposit(self, mock_create_bank_fees):
		from banking.overrides.bank_transaction import before_submit

		set_automatic_bank_fee_entries(True)
		bt = make_bank_transaction(
			bank_account=self.bank_account.name,
			withdrawal=2.0,
			included_fee=1.0,
			date="2025-01-01",
		)

		before_submit(bt, None)

		mock_create_bank_fees.assert_called_once()
