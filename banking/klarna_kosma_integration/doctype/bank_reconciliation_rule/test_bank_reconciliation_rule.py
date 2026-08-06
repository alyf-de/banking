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
from banking.testing_utils import TEST_COMPANY, create_bank_account, create_currency_account


def _group_account_with_parent(company: str) -> str:
	name = frappe.db.get_value(
		"Account",
		{"company": company, "is_group": 1, "parent_account": ["!=", ""]},
		"name",
	)
	if not name:
		raise RuntimeError(f"No suitable group Account found for company {company!r}")
	return name


def _resolved_test_company() -> str:
	if frappe.db.exists("Company", TEST_COMPANY):
		return TEST_COMPANY
	name = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	if not name:
		raise RuntimeError("No Company found for banking tests")
	return name


class TestBankReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		cls.test_company = _resolved_test_company()
		parent_account = _group_account_with_parent(cls.test_company)
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

	def _make_eur_target_and_rule(self, description: str, *, submit=True, disabled=0):
		parent_account = _group_account_with_parent(self.test_company)
		eur_target = create_currency_account("EUR", parent_account, f"_Test_BRR_Reapply_{description[:12]}")
		rule = frappe.new_doc("Bank Reconciliation Rule")
		rule.bank_account = self.ba.name
		rule.target_account = eur_target.name
		rule.disabled = disabled
		rule.filters = json.dumps([["Bank Transaction", "description", "=", description]])
		rule.insert(ignore_permissions=True, ignore_mandatory=True)
		if submit:
			rule.flags.ignore_permissions = True
			rule.submit()
		return rule, eur_target

	def _insert_unreconciled_bt(self, description: str, *, withdrawal=10.0, **extra):
		bt = frappe.new_doc("Bank Transaction")
		bt.company = self.test_company
		bt.bank_account = self.ba.name
		bt.withdrawal = withdrawal
		bt.date = "2025-06-01"
		bt.description = description
		bt.update(extra)
		bt.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
		frappe.db.set_value(
			"Bank Transaction",
			bt.name,
			{
				"docstatus": 1,
				"status": "Unreconciled",
				"unallocated_amount": withdrawal,
				"allocated_amount": 0,
			},
			update_modified=False,
		)
		return frappe.get_doc("Bank Transaction", bt.name)

	def test_reapply_to_unreconciled_dry_run_and_apply(self):
		desc = "REAPPLY-MATCH-001"
		rule, target = self._make_eur_target_and_rule(desc)
		matching = self._insert_unreconciled_bt(desc)
		self._insert_unreconciled_bt("REAPPLY-OTHER-001")

		preview = rule.reapply_to_unreconciled(dry_run=1)
		self.assertEqual(preview["count"], 1)

		bank_gl = frappe.db.get_value("Bank Account", self.ba.name, "account")

		def _stub_je(**kwargs):
			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Bank Entry"
			je.company = kwargs["company"]
			je.posting_date = kwargs["date"]
			je.append(
				"accounts",
				{
					"account": bank_gl,
					"debit_in_account_currency": kwargs.get("debit") or 0,
					"credit_in_account_currency": kwargs.get("credit") or 0,
				},
			)
			je.append(
				"accounts",
				{
					"account": target.name,
					"debit_in_account_currency": kwargs.get("credit") or 0,
					"credit_in_account_currency": kwargs.get("debit") or 0,
				},
			)
			je.insert(ignore_permissions=True)
			return je.name

		with patch(
			"banking.overrides.bank_transaction.create_automatic_journal_entry",
			side_effect=_stub_je,
		) as mock_je:
			result = rule.reapply_to_unreconciled()

		self.assertEqual(result["applied"], 1)
		self.assertEqual(result["skipped"], 0)
		self.assertEqual(result["failed"], 0)
		mock_je.assert_called_once()

		matching.reload()
		self.assertEqual(matching.status, "Reconciled")
		self.assertEqual(matching.unallocated_amount, 0)
		self.assertTrue(matching.payment_entries)

	def test_reapply_rolls_back_je_when_bt_save_fails(self):
		desc = "REAPPLY-ROLLBACK-001"
		rule, target = self._make_eur_target_and_rule(desc)
		bt = self._insert_unreconciled_bt(desc)
		bank_gl = frappe.db.get_value("Bank Account", self.ba.name, "account")
		created_jes: list[str] = []

		def _stub_je(**kwargs):
			je = frappe.new_doc("Journal Entry")
			je.voucher_type = "Bank Entry"
			je.company = kwargs["company"]
			je.posting_date = kwargs["date"]
			je.append(
				"accounts",
				{
					"account": bank_gl,
					"debit_in_account_currency": kwargs.get("debit") or 0,
					"credit_in_account_currency": kwargs.get("credit") or 0,
				},
			)
			je.append(
				"accounts",
				{
					"account": target.name,
					"debit_in_account_currency": kwargs.get("credit") or 0,
					"credit_in_account_currency": kwargs.get("debit") or 0,
				},
			)
			je.insert(ignore_permissions=True)
			created_jes.append(je.name)
			return je.name

		original_save = frappe.model.document.Document.save

		def _save(self, *args, **kwargs):
			if self.doctype == "Bank Transaction":
				raise frappe.ValidationError("simulated save failure")
			return original_save(self, *args, **kwargs)

		with (
			patch(
				"banking.overrides.bank_transaction.create_automatic_journal_entry",
				side_effect=_stub_je,
			),
			patch.object(frappe.model.document.Document, "save", _save),
		):
			result = rule.reapply_to_unreconciled()

		self.assertEqual(result["applied"], 0)
		self.assertEqual(result["failed"], 1)
		self.assertTrue(created_jes)
		self.assertFalse(frappe.db.exists("Journal Entry", created_jes[0]))

		bt.reload()
		self.assertEqual(bt.status, "Unreconciled")
		self.assertFalse(bt.payment_entries)

	def test_reapply_rejects_draft_and_disabled(self):
		desc = "REAPPLY-GUARD-001"
		draft_rule, _ = self._make_eur_target_and_rule(desc, submit=False)
		with self.assertRaises(frappe.ValidationError):
			draft_rule.reapply_to_unreconciled(dry_run=1)

		disabled_rule, _ = self._make_eur_target_and_rule("REAPPLY-GUARD-002", disabled=1)
		with self.assertRaises(frappe.ValidationError):
			disabled_rule.reapply_to_unreconciled(dry_run=1)

	def test_reapply_skips_reserved_and_party_mismatch(self):
		desc = "REAPPLY-SKIP-001"
		parent_account = _group_account_with_parent(self.test_company)
		payable = create_currency_account(
			"EUR", parent_account, "_Test_BRR_Reapply_Pay", account_type="Payable"
		)
		rule = frappe.new_doc("Bank Reconciliation Rule")
		rule.bank_account = self.ba.name
		rule.target_account = payable.name
		rule.filters = json.dumps([["Bank Transaction", "description", "=", desc]])
		# Bypass party validation on save by setting party_type filter for rule validity,
		# then apply to a BT without party.
		rule.filters = json.dumps(
			[
				["Bank Transaction", "description", "=", desc],
				["Bank Transaction", "party_type", "=", "Supplier"],
			]
		)
		rule.insert(ignore_permissions=True, ignore_mandatory=True)
		rule.flags.ignore_permissions = True
		rule.submit()

		reserved = self._insert_unreconciled_bt(desc, party_type="Supplier")
		frappe.db.set_value(
			"Bank Transaction",
			reserved.name,
			{"reserved_voucher_type": "Journal Entry", "reserved_voucher": "JE-RESERVED"},
			update_modified=False,
		)

		self._insert_unreconciled_bt(desc, withdrawal=7.0, party_type="Supplier")

		with patch("banking.overrides.bank_transaction.create_automatic_journal_entry") as mock_je:
			result = rule.reapply_to_unreconciled()

		mock_je.assert_not_called()
		self.assertEqual(result["applied"], 0)
		self.assertEqual(result["skipped"], 2)
		self.assertEqual(result["failed"], 0)
