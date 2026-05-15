# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError
from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	BankReconciliationRule,
	NoFiltersError,
	get_bank_transaction_match_stats,
)
from banking.testing_utils import TEST_COMPANY, create_bank_account, create_currency_account


def _group_account_with_parent(company: str) -> str:
	row = frappe.db.sql(
		"""
		select name from `tabAccount`
		where company = %s and is_group = 1 and ifnull(parent_account, '') != ''
		limit 1
		""",
		(company,),
	)
	if not row:
		raise RuntimeError(f"No suitable group Account found for company {company!r}")
	return row[0][0]


def _resolved_test_company() -> str:
	if frappe.db.exists("Company", TEST_COMPANY):
		return TEST_COMPANY
	row = frappe.db.sql("select name from `tabCompany` order by creation asc limit 1")
	if not row:
		raise RuntimeError("No Company found for banking tests")
	return row[0][0]


class TestBankReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		cls.test_company = _resolved_test_company()
		parent_account = _group_account_with_parent(cls.test_company)
		bank_account = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.target_account = create_currency_account("USD", parent_account, "_Test_Account_USD")
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

	@patch(
		"banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule.today",
		return_value="2025-06-15",
	)
	def test_get_bank_transaction_match_stats_windows(self, _mock_today):
		desc = "STAT-COUNT-BRR-359"
		filters = json.dumps([["Bank Transaction", "description", "=", desc, False]])

		def _insert_submitted_bt(posting_date: str):
			bt = frappe.new_doc("Bank Transaction")
			bt.company = self.test_company
			bt.bank_account = self.ba.name
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
		parent_account = _group_account_with_parent(self.test_company)
		eur_target = create_currency_account("EUR", parent_account, "_Test_BRR_EUR_Tgt_Mis")
		other_bank_acc = create_currency_account("EUR", parent_account, "_Test_Account_EUR_BrrMis")
		other_ba = frappe.new_doc("Bank Account")
		other_ba.account_name = "_Test_B_Other_Mismatch"
		other_ba.account = other_bank_acc.name
		other_ba.bank = "_Test_Bank"
		other_ba.is_company_account = 1
		other_ba.insert(ignore_permissions=True, ignore_links=True)
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
