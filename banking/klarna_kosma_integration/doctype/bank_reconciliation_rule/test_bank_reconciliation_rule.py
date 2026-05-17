# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError
from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	NoFiltersError,
	get_rules_for_reorder,
	reorder_bank_reconciliation_rule_priorities,
)
from banking.testing_utils import TEST_COMPANY, create_bank_account, create_currency_account


class TestBankReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		bank_account = create_currency_account("EUR", parent_account, "_Test_Account_EUR")
		cls.target_account = create_currency_account("USD", parent_account, "_Test_Account_USD")
		cls.target_eur = create_currency_account("EUR", parent_account, "_Test_BRR_Target_EUR")
		cls.ba = create_bank_account(bank_account.name)

	def test_validate_account_currencies(self):
		brr_doc = frappe.new_doc("Bank Reconciliation Rule")
		brr_doc.bank_account = self.ba.name
		brr_doc.target_account = self.target_account.name

		with self.assertRaises(CurrencyMismatchError):
			brr_doc.validate_account_currencies()

	def test_validate_filters(self):
		brr_doc = frappe.new_doc("Bank Reconciliation Rule")
		brr_doc.filters = None
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()

		brr_doc.filters = "[]"
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()

	def _insert_draft_rule(self, description_value: str, priority: int):
		r = frappe.new_doc("Bank Reconciliation Rule")
		r.bank_account = self.ba.name
		r.target_account = self.target_eur.name
		r.filters = f'[["Bank Transaction","description","=","{description_value}",false]]'
		r.priority = priority
		r.insert(ignore_permissions=True, ignore_mandatory=True)
		return r

	def test_reorder_priorities(self):
		frappe.db.delete("Bank Reconciliation Rule", {"bank_account": self.ba.name})
		r1 = self._insert_draft_rule("BRR-REORDER-1", 2)
		r2 = self._insert_draft_rule("BRR-REORDER-2", 1)
		self.assertEqual(
			[x["name"] for x in get_rules_for_reorder(bank_account=self.ba.name)], [r1.name, r2.name]
		)
		reorder_bank_reconciliation_rule_priorities(
			bank_account=self.ba.name, ordered_names=[r2.name, r1.name]
		)
		self.assertEqual(frappe.db.get_value("Bank Reconciliation Rule", r2.name, "priority"), 20)
		self.assertEqual(frappe.db.get_value("Bank Reconciliation Rule", r1.name, "priority"), 10)

	def test_reorder_priorities_submitted(self):
		frappe.db.delete("Bank Reconciliation Rule", {"bank_account": self.ba.name})
		r1 = self._insert_draft_rule("BRR-REORDER-SUB-1", 2)
		r2 = self._insert_draft_rule("BRR-REORDER-SUB-2", 1)
		r1.submit()
		r2.submit()
		self.assertEqual(r1.docstatus, 1)
		self.assertEqual(r2.docstatus, 1)

		reorder_bank_reconciliation_rule_priorities(
			bank_account=self.ba.name, ordered_names=[r2.name, r1.name]
		)
		self.assertEqual(frappe.db.get_value("Bank Reconciliation Rule", r2.name, "priority"), 20)
		self.assertEqual(frappe.db.get_value("Bank Reconciliation Rule", r1.name, "priority"), 10)
		self.assertEqual(frappe.db.get_value("Bank Reconciliation Rule", r2.name, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Bank Reconciliation Rule", r1.name, "docstatus"), 1)
