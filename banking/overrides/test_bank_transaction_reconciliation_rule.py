# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.testing_utils import (
	create_bank_account,
	create_currency_account,
	create_supplier,
)

test_dependencies = ["Company", "Account"]


def create_bank_reconciliation_rule(bank_account, target_account, filters, disabled=0, submit=True):
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
	doc.company = "_Test Company"
	doc.update(values)
	if insert:
		doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return doc


class TestBankTransactionReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": "_Test Company"})
		cls.account_main = create_currency_account("INR", parent_account, "_Test_Account_INR")
		cls.account_target = create_currency_account("INR", parent_account, "_Test_Account_INR_Target")
		cls.account_payable = create_currency_account(
			"INR", parent_account, "_Test_Account_INR_Payable", account_type="Payable"
		)
		cls.bank_account = create_bank_account(cls.account_main.name)
		cls.supplier = create_supplier()

	@patch("banking.overrides.bank_transaction.create_je_automatic_rules")
	def test_before_submit_invokes_rule_engine(self, mock_create_auto_rules):
		from banking.overrides.bank_transaction import before_submit

		bt = create_bank_transaction(insert=False)

		with self.assertRaises(frappe.ValidationError):
			before_submit(bt, None)

		bt.bank_account = self.bank_account.name
		bt.deposit = 1.0
		before_submit(bt, None)

		mock_create_auto_rules.assert_called_once()

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_automatic_rules_withdrawal(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_automatic_rules

		frappe.db.delete("Bank Reconciliation Rule", {"bank_account": self.bank_account.name})
		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		brr_1 = create_bank_reconciliation_rule(
			self.bank_account.name,
			self.account_target.name,
			'[["Bank Transaction","description","=","FLAG-TRUE"]]',
		)

		create_bank_reconciliation_rule(
			self.bank_account.name,
			self.account_main.name,
			'[["Bank Transaction","description","=","FLAG-TRUE"]]',
			disabled=1,
		)
		create_bank_reconciliation_rule(
			self.bank_account.name,
			self.account_main.name,
			'[["Bank Transaction","description","=","FLAG-TRUE"]]',
			submit=False,
		)

		bt = create_bank_transaction(
			withdrawal=5.0,
			bank_account=self.bank_account.name,
			description="FLAG-TRUE",
		)
		cost_center = frappe.get_cached_value("Company", bt.company, "cost_center")

		create_je_automatic_rules(bt, cost_center, date, self.account_main.name, 0, bt.withdrawal)

		mock_create_je.assert_called_once_with(
			company=bt.company,
			bank_account=bt.bank_account,
			bank_transaction=bt.name,
			cost_center=cost_center,
			date=date,
			account=self.account_main.name,
			target_account=self.account_target.name,
			debit=0.0,
			credit=5.0,
			rule=brr_1.name,
		)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 5.0)
		self.assertEqual(bt.allocated_amount, 5.0)
		self.assertEqual(bt.status, "Reconciled")

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_automatic_rules_sets_party_for_payable_account(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_automatic_rules

		frappe.db.delete("Bank Reconciliation Rule", {"bank_account": self.bank_account.name})
		mock_create_je.return_value = "JE-TEST-0002"

		create_bank_reconciliation_rule(
			self.bank_account.name,
			self.account_payable.name,
			'[["Bank Transaction","party_type","=","Supplier",false]]',
		)

		bt = create_bank_transaction(
			withdrawal=5.0,
			bank_account=self.bank_account.name,
			party_type="Supplier",
			party=self.supplier.name,
		)
		cost_center = frappe.get_cached_value("Company", bt.company, "cost_center")

		create_je_automatic_rules(bt, cost_center, "2025-01-01", self.account_main.name, 0, bt.withdrawal)

		self.assertEqual(mock_create_je.call_args.kwargs["party_type"], "Supplier")
		self.assertEqual(mock_create_je.call_args.kwargs["party"], self.supplier.name)

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_automatic_rules_skips_payable_account_without_party(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_automatic_rules

		frappe.db.delete("Bank Reconciliation Rule", {"bank_account": self.bank_account.name})

		create_bank_reconciliation_rule(
			self.bank_account.name,
			self.account_payable.name,
			'[["Bank Transaction","party_type","=","Supplier",false]]',
		)

		bt = create_bank_transaction(
			withdrawal=5.0,
			bank_account=self.bank_account.name,
			party_type="Supplier",
		)
		cost_center = frappe.get_cached_value("Company", bt.company, "cost_center")

		create_je_automatic_rules(bt, cost_center, "2025-01-01", self.account_main.name, 0, bt.withdrawal)

		mock_create_je.assert_not_called()
		self.assertFalse(bt.payment_entries)

	@patch("banking.overrides.bank_transaction.create_automatic_journal_entry")
	def test_create_je_automatic_rules_deposit(self, mock_create_je):
		from banking.overrides.bank_transaction import create_je_automatic_rules

		frappe.db.delete("Bank Reconciliation Rule", {"bank_account": self.bank_account.name})
		mock_create_je.return_value = "JE-TEST-0001"
		date = "2025-01-01"

		brr_1 = create_bank_reconciliation_rule(
			self.bank_account.name,
			self.account_target.name,
			'[["Bank Transaction","description","=","FLAG-TRUE"]]',
		)

		bt = create_bank_transaction(
			deposit=5.0,
			bank_account=self.bank_account.name,
			description="FLAG-TRUE",
		)
		cost_center = frappe.get_cached_value("Company", bt.company, "cost_center")

		create_je_automatic_rules(bt, cost_center, date, self.account_main.name, bt.deposit, 0)

		mock_create_je.assert_called_once_with(
			company=bt.company,
			bank_account=bt.bank_account,
			bank_transaction=bt.name,
			cost_center=cost_center,
			date=date,
			account=self.account_main.name,
			target_account=self.account_target.name,
			debit=5.0,
			credit=0.0,
			rule=brr_1.name,
		)
		self.assertEqual(bt.payment_entries[0].payment_entry, "JE-TEST-0001")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 5.0)
		self.assertEqual(bt.allocated_amount, 5.0)
		self.assertEqual(bt.status, "Reconciled")
