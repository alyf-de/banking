# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.utils import create_bank_account, create_currency_account


class TestBankReconciliationRule(FrappeTestCase):
	def test_ensure_positive_deposit_withdrawal_fees(self):
		from banking.overrides.bank_transaction import ensure_positive_deposit_withdrawal_fees

		doc = frappe.new_doc("Bank Transaction")
		doc.deposit = -2.0
		doc.withdrawal = 0.0
		doc.included_fee = -1.0
		doc.excluded_fee = -1.0

		ensure_positive_deposit_withdrawal_fees(doc, None)

		self.assertEqual(doc.deposit, 1.0)
		self.assertEqual(doc.withdrawal, 0.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)

		doc.deposit = 0.0
		doc.withdrawal = -1.0
		doc.included_fee = -1.0
		doc.excluded_fee = -1.0

		ensure_positive_deposit_withdrawal_fees(doc, None)

		self.assertEqual(doc.deposit, 0.0)
		self.assertEqual(doc.withdrawal, 2.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)

		doc.deposit = None
		doc.withdrawal = None
		doc.included_fee = None
		doc.excluded_fee = None

		ensure_positive_deposit_withdrawal_fees(doc, None)

		self.assertEqual(doc.deposit, 0.0)
		self.assertEqual(doc.withdrawal, 0.0)
		self.assertEqual(doc.included_fee, 0.0)
		self.assertEqual(doc.excluded_fee, 0.0)

	@patch("banking.overrides.bank_transaction.create_je_automatic_rules")
	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_before_submit(self, mock_create_bank_fees, mock_create_auto_rules):
		from banking.overrides.bank_transaction import before_submit

		parent_account = frappe.db.get_value("Account", {"is_group": 1})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_2.name)

		bt = frappe.new_doc("Bank Transaction")
		bt.company = "_Test Company"

		with self.assertRaises(
			frappe.ValidationError,
			msg="Expected ValidationError when bank account is missing.",
		):
			before_submit(bt, None)

		bt.bank_account = ba.name
		bt.deposit = -1.0

		with self.assertRaises(
			frappe.ValidationError,
			msg="Expected ValidationError for negative deposit.",
		):
			before_submit(bt, None)

		bt.deposit = 0.0
		bt.withdrawal = -1.0

		with self.assertRaises(
			frappe.ValidationError,
			msg="Expected ValidationError for negative withdrawal.",
		):
			before_submit(bt, None)

		bt.withdrawal = 1.0

		before_submit(bt, None)
		mock_create_bank_fees.assert_called_once()
		mock_create_auto_rules.assert_called_once()

		ba.delete(delete_permanently=True, ignore_permissions=True)
		account_1.delete(delete_permanently=True, ignore_permissions=True)
		account_2.delete(delete_permanently=True, ignore_permissions=True)

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_bank_fees_withdrawal(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_bank_fees

		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		parent_account = frappe.db.get_value("Account", {"is_group": 1})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_2.name)

		bt = frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"company": "_Test Company",
				"withdrawal": 5.0,
				"included_fee": 1.0,
				"bank_account": ba.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		company_doc = frappe.get_cached_doc("Company", bt.company)

		# Assert regular entry
		create_je_bank_fees(bt, company_doc, date, account_1, 0, bt.withdrawal)

		mock_create_je.assert_called_once_with(
			bt,
			company_doc,
			date,
			account_1,
			account_2.name,
			None,
			0,
			1.0,
		)

		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 1.0)
		self.assertEqual(bt.allocated_amount, 1.0)
		self.assertEqual(bt.unallocated_amount, 4.0)
		self.assertEqual(bt.status, "Pending")

		# Assert fee = full amount entry
		bt.withdrawal = 1.0
		create_je_bank_fees(bt, company_doc, date, account_1, 0, bt.withdrawal)

		self.assertEqual(bt.allocated_amount, 1.0)
		self.assertEqual(bt.unallocated_amount, 0.0)
		self.assertEqual(bt.status, "Reconciled")

		ba.delete(delete_permanently=True, ignore_permissions=True)
		account_1.delete(delete_permanently=True, ignore_permissions=True)
		account_2.delete(delete_permanently=True, ignore_permissions=True)

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_bank_fees_deposit(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_bank_fees

		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		parent_account = frappe.db.get_value("Account", {"is_group": 1})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_2.name)

		bt = frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"company": "_Test Company",
				"deposit": 5.0,
				"included_fee": 1.0,
				"bank_account": ba.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		company_doc = frappe.get_cached_doc("Company", bt.company)

		# Assert regular entry
		create_je_bank_fees(bt, company_doc, date, account_1, bt.deposit, 0)

		mock_create_je.assert_called_once_with(
			bt,
			company_doc,
			date,
			account_1,
			account_2.name,
			None,
			0,
			1.0,
		)

		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 0.0)
		self.assertEqual(bt.allocated_amount, 0.0)
		self.assertEqual(bt.unallocated_amount, 5.0)
		self.assertEqual(bt.status, "Pending")

		ba.delete(delete_permanently=True, ignore_permissions=True)
		account_1.delete(delete_permanently=True, ignore_permissions=True)
		account_2.delete(delete_permanently=True, ignore_permissions=True)

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_automatic_rules_withdrawal(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_automatic_rules

		frappe.db.delete("Bank Reconciliation Rule")

		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		parent_account = frappe.db.get_value("Account", {"is_group": 1})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_1.name)

		# brr_1 => correct
		brr_1 = frappe.get_doc(
			{
				"doctype": "Bank Reconciliation Rule",
				"disabled": 0,
				"bank_account": ba.name,
				"docstatus": 1,
				"target_account": account_2.name,
				"filters": '[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		# brr_2 => fail
		frappe.get_doc(
			{
				"doctype": "Bank Reconciliation Rule",
				"disabled": 1,
				"bank_account": ba.name,
				"docstatus": 1,
				"target_account": account_1.name,
				"filters": '[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		# brr_3 => fail
		frappe.get_doc(
			{
				"doctype": "Bank Reconciliation Rule",
				"disabled": 0,
				"bank_account": ba.name,
				"docstatus": 0,
				"target_account": account_1.name,
				"filters": '[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		bt = frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"company": "_Test Company",
				"withdrawal": 5.0,
				"included_fee": 1.0,
				"bank_account": ba.name,
				"description": "FLAG-TRUE",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		company_doc = frappe.get_cached_doc("Company", bt.company)

		# Assert regular entry
		create_je_automatic_rules(bt, company_doc, date, account_1, 0, bt.withdrawal - bt.included_fee)

		mock_create_je.assert_called_once_with(
			bt,
			company_doc,
			date,
			account_1,
			account_2.name,
			brr_1.name,
			0.0,
			4.0,
		)

		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 4.0)
		self.assertEqual(bt.allocated_amount, 4.0)
		self.assertEqual(bt.status, "Reconciled")

		ba.delete(delete_permanently=True, ignore_permissions=True)
		account_1.delete(delete_permanently=True, ignore_permissions=True)
		account_2.delete(delete_permanently=True, ignore_permissions=True)

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_automatic_rules_deposit(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_automatic_rules

		frappe.db.delete("Bank Reconciliation Rule")

		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		parent_account = frappe.db.get_value("Account", {"is_group": 1})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_1.name)

		# brr_1 => correct
		brr_1 = frappe.get_doc(
			{
				"doctype": "Bank Reconciliation Rule",
				"disabled": 0,
				"bank_account": ba.name,
				"docstatus": 1,
				"target_account": account_2.name,
				"filters": '[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		# brr_2 => fail
		frappe.get_doc(
			{
				"doctype": "Bank Reconciliation Rule",
				"disabled": 1,
				"bank_account": ba.name,
				"docstatus": 1,
				"target_account": account_1.name,
				"filters": '[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		# brr_3 => fail
		frappe.get_doc(
			{
				"doctype": "Bank Reconciliation Rule",
				"disabled": 0,
				"bank_account": ba.name,
				"docstatus": 0,
				"target_account": account_1.name,
				"filters": '[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		bt = frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"company": "_Test Company",
				"deposit": 5.0,
				"included_fee": 1.0,
				"bank_account": ba.name,
				"description": "FLAG-TRUE",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		company_doc = frappe.get_cached_doc("Company", bt.company)

		# Assert regular entry
		create_je_automatic_rules(bt, company_doc, date, account_1, bt.deposit, 0)

		mock_create_je.assert_called_once_with(
			bt,
			company_doc,
			date,
			account_1,
			account_2.name,
			brr_1.name,
			5.0,
			0.0,
		)

		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 5.0)
		self.assertEqual(bt.allocated_amount, 5.0)
		self.assertEqual(bt.status, "Reconciled")

		ba.delete(delete_permanently=True, ignore_permissions=True)
		account_1.delete(delete_permanently=True, ignore_permissions=True)
		account_2.delete(delete_permanently=True, ignore_permissions=True)
