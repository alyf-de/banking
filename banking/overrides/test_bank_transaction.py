# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.utils import TEST_COMPANY, create_bank_account, create_currency_account


def create_bank_reconciliation_rule(
	bank_account,
	target_account,
	filters,
	disabled=0,
	submit=True,
):
	rule = frappe.new_doc("Bank Reconciliation Rule")
	rule.disabled = disabled
	rule.bank_account = bank_account
	rule.target_account = target_account
	rule.filters = filters
	rule.insert(ignore_permissions=True, ignore_mandatory=True)
	if submit:
		rule.flags.ignore_permissions = True
		rule.flags.ignore_mandatory = True
		rule.submit()
	return rule


def create_bank_transaction(insert=True, **values):
	doc = frappe.new_doc("Bank Transaction")
	doc.company = TEST_COMPANY
	doc.update(values)
	if insert:
		doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return doc


class TestBankReconciliationRule(FrappeTestCase):
	def test_enforce_positive_values(self):
		from banking.overrides.bank_transaction import enforce_positive_values

		doc = create_bank_transaction(insert=False)
		doc.deposit = -2.0
		doc.withdrawal = 0.0
		doc.included_fee = -1.0
		doc.excluded_fee = -1.0

		enforce_positive_values(doc)

		self.assertEqual(doc.deposit, 1.0)
		self.assertEqual(doc.withdrawal, 0.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)

		doc.deposit = 0.0
		doc.withdrawal = -1.0
		doc.included_fee = -1.0
		doc.excluded_fee = -1.0

		enforce_positive_values(doc)

		self.assertEqual(doc.deposit, 0.0)
		self.assertEqual(doc.withdrawal, 2.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)

		doc.deposit = None
		doc.withdrawal = None
		doc.included_fee = None
		doc.excluded_fee = None

		enforce_positive_values(doc)

		self.assertEqual(doc.deposit, None)
		self.assertEqual(doc.withdrawal, None)
		self.assertEqual(doc.included_fee, None)
		self.assertEqual(doc.excluded_fee, None)

	@patch("banking.overrides.bank_transaction.create_je_automatic_rules")
	@patch("banking.overrides.bank_transaction.create_je_bank_fees")
	def test_before_submit(self, mock_create_bank_fees, mock_create_auto_rules):
		from banking.overrides.bank_transaction import before_submit

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_2.name)

		bt = create_bank_transaction(insert=False)

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

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_2.name)

		bt = create_bank_transaction(withdrawal=5.0, included_fee=1.0, bank_account=ba.name)

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

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_2.name)

		bt = create_bank_transaction(deposit=5.0, included_fee=1.0, bank_account=ba.name)

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

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_1.name)

		# brr_1 => correct
		brr_1 = create_bank_reconciliation_rule(
			ba.name,
			account_2.name,
			'[["Bank Transaction","description","=","FLAG-TRUE",false]]',
		)

		# brr_2 => fail
		create_bank_reconciliation_rule(
			ba.name,
			account_1.name,
			'[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			disabled=1,
		)

		# brr_3 => fail
		create_bank_reconciliation_rule(
			ba.name,
			account_1.name,
			'[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			submit=False,
		)

		bt = create_bank_transaction(
			withdrawal=5.0,
			included_fee=1.0,
			bank_account=ba.name,
			description="FLAG-TRUE",
		)

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

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account(
			"EUR",
			parent_account,
			account_name="_Test_Account_EUR_Fee",
		)
		ba = create_bank_account(account_1.name, bank_fee_account=account_1.name)

		# brr_1 => correct
		brr_1 = create_bank_reconciliation_rule(
			ba.name,
			account_2.name,
			'[["Bank Transaction","description","=","FLAG-TRUE",false]]',
		)

		# brr_2 => fail
		create_bank_reconciliation_rule(
			ba.name,
			account_1.name,
			'[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			disabled=1,
		)

		# brr_3 => fail
		create_bank_reconciliation_rule(
			ba.name,
			account_1.name,
			'[["Bank Transaction","description","=","FLAG-TRUE",false]]',
			submit=False,
		)

		bt = create_bank_transaction(
			deposit=5.0,
			included_fee=1.0,
			bank_account=ba.name,
			description="FLAG-TRUE",
		)

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
