# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError, PartyMismatchError
from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	BankReconciliationRule,
	NoFiltersError,
	get_bank_transaction_match_stats,
)
from banking.testing_utils import create_bank_account, create_currency_account

test_dependencies = ["Company", "Account"]


class TestBankReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": "_Test Company"})
		bank_account = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.target_account = create_currency_account("USD", parent_account, "_Test_Account_USD")
		cls.payable_account = create_currency_account(
			"EUR", parent_account, "_Test_Account_EUR_Payable_Brr", account_type="Payable"
		)
		cls.ba = create_bank_account(bank_account.name)

	def test_validate_account_currencies(self):
		brr_doc = BankReconciliationRule(
			{
				"doctype": "Bank Reconciliation Rule",
				"bank_account": self.ba.name,
				"target_account": self.target_account.name,
			}
		)

		with self.assertRaises(CurrencyMismatchError):
			brr_doc.validate_account_currencies()

	def test_validate_filters(self):
		brr_doc = BankReconciliationRule({"doctype": "Bank Reconciliation Rule"})
		brr_doc.filters = None
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()

		brr_doc.filters = "[]"
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()

	def test_validate_target_account_party(self):
		def rule(filters: list) -> BankReconciliationRule:
			return BankReconciliationRule(
				{
					"doctype": "Bank Reconciliation Rule",
					"bank_account": self.ba.name,
					"target_account": self.payable_account.name,
					"filters": json.dumps(filters),
				}
			)

		without_party_filter = rule([["Bank Transaction", "description", "=", "X"]])
		with self.assertRaises(PartyMismatchError):
			without_party_filter.validate_target_account_party()

		wrong_party_type = rule([["Bank Transaction", "party_type", "=", "Customer"]])
		with self.assertRaises(PartyMismatchError):
			wrong_party_type.validate_target_account_party()

		rule([["Bank Transaction", "party_type", "=", "Supplier"]]).validate_target_account_party()

	def test_validate_target_account_party_ignores_other_accounts(self):
		brr_doc = BankReconciliationRule(
			{
				"doctype": "Bank Reconciliation Rule",
				"bank_account": self.ba.name,
				"target_account": self.target_account.name,
				"filters": json.dumps([["Bank Transaction", "description", "=", "X"]]),
			}
		)

		brr_doc.validate_target_account_party()

	@patch(
		"banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule.today",
		return_value="2025-06-15",
	)
	def test_get_bank_transaction_match_stats_windows(self, _mock_today):
		desc = "STAT-COUNT-BRR-359"
		filters = json.dumps([["Bank Transaction", "description", "=", desc]])

		def _insert_submitted_bt(posting_date: str):
			bt = frappe.new_doc("Bank Transaction")
			bt.company = "_Test Company"
			bt.bank_account = self.ba.name
			bt.currency = "EUR"
			bt.deposit = 1.0
			bt.date = posting_date
			bt.description = desc
			bt.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
			frappe.db.set_value("Bank Transaction", bt.name, "docstatus", 1, update_modified=False)

		try:
			_insert_submitted_bt("2025-06-10")
			_insert_submitted_bt("2025-05-01")
			_insert_submitted_bt("2024-01-01")

			stats = get_bank_transaction_match_stats(self.ba.name, filters)
			self.assertEqual(stats["last_30_days"], 1)
			self.assertEqual(stats["last_12_months"], 2)
			self.assertEqual(str(stats["as_of"]), "2025-06-15")
		finally:
			frappe.db.delete("Bank Transaction", {"description": desc})

	def test_get_bank_transaction_match_stats_bank_account_mismatch(self):
		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": "_Test Company"})
		eur_target = create_currency_account("EUR", parent_account, "_Test_BRR_EUR_Tgt_Mis")
		other_bank_acc = create_currency_account("EUR", parent_account, "_Test_Account_EUR_BrrMis")
		other_ba = create_bank_account(other_bank_acc.name, account_name="_Test_B_Other_Mismatch")
		rule = frappe.new_doc("Bank Reconciliation Rule")
		rule.bank_account = self.ba.name
		rule.target_account = eur_target.name
		rule.filters = json.dumps([["Bank Transaction", "description", "=", "X"]])
		rule.insert(ignore_permissions=True, ignore_mandatory=True)
		rule.flags.ignore_permissions = True
		rule.submit()
		try:
			with self.assertRaises(frappe.ValidationError):
				get_bank_transaction_match_stats(
					other_ba.name,
					rule.filters,
					bank_reconciliation_rule=rule.name,
				)
		finally:
			rule.cancel()
			frappe.delete_doc("Bank Reconciliation Rule", rule.name, force=1, ignore_permissions=True)
			frappe.delete_doc("Bank Account", other_ba.name, force=1, ignore_permissions=True)
			frappe.delete_doc("Account", other_bank_acc.name, force=1, ignore_permissions=True)
			frappe.delete_doc("Account", eur_target.name, force=1, ignore_permissions=True)
