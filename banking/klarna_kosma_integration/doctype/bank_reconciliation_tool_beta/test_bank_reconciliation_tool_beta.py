# Copyright (c) 2023, ALYF GmbH and Contributors
# See license.txt
import json
from unittest.mock import patch

import frappe
from erpnext.accounts.doctype.payment_entry.test_payment_entry import (
	create_payment_entry,
)
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import (
	make_purchase_invoice,
)
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import (
	create_sales_invoice,
)
from erpnext.accounts.test.accounts_mixin import AccountsTestMixin
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate
from hrms.hr.doctype.expense_claim.test_expense_claim import make_expense_claim

from banking.exceptions import CurrencyMismatchError, FullReconciliationRequiredError
from banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta import (
	_merge_accounting_dimensions_into_je_accounts,
	_merge_accounting_dimensions_into_payment_entry,
	auto_reconcile_vouchers,
	bulk_reconcile_vouchers,
	create_journal_entry_bts,
	create_payment_entry_bts,
	get_linked_payments,
)

test_dependencies = ["Warehouse", "Item", "Account", "Cost Center", "UOM", "Company"]


class TestBankReconciliationToolBeta(AccountsTestMixin, FrappeTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()

		create_custom_field(
			"Sales Invoice", dict(fieldname="custom_ref_no", label="Ref No", fieldtype="Data")
		)  # commits to db internally

		create_bank()
		cls.gl_account = create_bank_gl_account("_Test Bank Reco Tool")
		cls.bank_account = create_bank_account(gl_account=cls.gl_account)
		cls.customer = create_customer(customer_name="ABC Inc.")

		cls.create_item(cls, item_name="Reco Item", company="_Test Company", warehouse="Finished Goods - _TC")
		frappe.db.savepoint(save_point="bank_reco_beta_before_tests")

	def tearDown(self) -> None:
		"""Runs after each test."""
		# Make sure invoices are rolled back to not affect invoice count assertions
		frappe.db.rollback(save_point="bank_reco_beta_before_tests")

	def test_unpaid_invoices_more_than_transaction(self):
		"""
		Test unpaid invoices fully reconcile.
		BT: 150
		SI1, SI2: 100, 100 (200) (partial: 150)
		"""
		doc = create_bank_transaction(
			date=add_days(getdate(), -2), deposit=150, bank_account=self.bank_account
		)
		customer = create_customer()
		si = create_sales_invoice(
			rate=100,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)
		si2 = create_sales_invoice(
			rate=100,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		bulk_reconcile_vouchers(
			doc.name,
			json.dumps(
				[
					{"payment_doctype": "Sales Invoice", "payment_name": si.name},
					{"payment_doctype": "Sales Invoice", "payment_name": si2.name},
				]
			),
		)

		doc.reload()
		self.assertEqual(len(doc.payment_entries), 1)  # 1 PE made against 2 invoices
		self.assertEqual(doc.payment_entries[0].allocated_amount, 150)

		pe = get_pe_references([si.name, si2.name])
		self.assertEqual(pe[0].allocated_amount, 100)
		self.assertEqual(pe[1].allocated_amount, 50)
		# Check if the PE is posted on the same date as the BT
		self.assertEqual(
			doc.date,
			frappe.db.get_value("Payment Entry", doc.payment_entries[0].payment_entry, "posting_date"),
		)

	def test_unpaid_invoices_less_than_transaction(self):
		"""
		Test if unpaid invoices partially reconcile.
		BT: 100
		SI1, SI2: 50, 20 (70)
		"""
		doc = create_bank_transaction(deposit=100, bank_account=self.bank_account)
		customer = create_customer()
		si = create_sales_invoice(
			rate=50,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)
		si2 = create_sales_invoice(
			rate=20,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		bulk_reconcile_vouchers(
			doc.name,
			json.dumps(
				[
					{"payment_doctype": "Sales Invoice", "payment_name": si.name},
					{"payment_doctype": "Sales Invoice", "payment_name": si2.name},
				]
			),
		)

		doc.reload()
		self.assertEqual(doc.payment_entries[0].allocated_amount, 70)
		self.assertEqual(doc.unallocated_amount, 30)

		pe = get_pe_references([si.name, si2.name])
		self.assertEqual(pe[0].allocated_amount, 50)
		self.assertEqual(pe[1].allocated_amount, 20)

	def test_multiple_transactions_one_unpaid_invoice(self):
		"""
		Test if multiple transactions reconcile with one unpaid invoice.
		"""
		bt1 = create_bank_transaction(deposit=100, bank_account=self.bank_account)
		bt2 = create_bank_transaction(deposit=100, bank_account=self.bank_account)

		customer = create_customer()
		si = create_sales_invoice(
			rate=200,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)
		bulk_reconcile_vouchers(
			bt1.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)
		bt1.reload()
		si.reload()
		self.assertEqual(bt1.payment_entries[0].allocated_amount, 100)
		self.assertEqual(si.outstanding_amount, 100)

		bulk_reconcile_vouchers(
			bt2.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)
		bt2.reload()
		si.reload()
		self.assertEqual(bt2.payment_entries[0].allocated_amount, 100)
		self.assertEqual(si.outstanding_amount, 0)

	def test_single_transaction_multiple_payment_vouchers(self):
		"""
		Test if single transaction partially reconciles with multiple payment vouchers.
		"""
		pe = create_payment_entry(
			payment_type="Receive",
			party_type="Customer",
			party=self.customer,
			paid_from="Debtors - _TC",
			paid_to=self.gl_account,
			paid_amount=50,
			save=1,
			submit=1,
		)
		pe2 = create_payment_entry(
			payment_type="Receive",
			party_type="Customer",
			party=self.customer,
			paid_from="Debtors - _TC",
			paid_to=self.gl_account,
			paid_amount=30,
			save=1,
			submit=1,
		)
		bt = create_bank_transaction(deposit=100, bank_account=self.bank_account)
		bulk_reconcile_vouchers(
			bt.name,
			json.dumps(
				[
					{"payment_doctype": "Payment Entry", "payment_name": pe.name},
					{"payment_doctype": "Payment Entry", "payment_name": pe2.name},
				]
			),
		)

		bt.reload()
		self.assertEqual(bt.payment_entries[0].allocated_amount, 50)
		self.assertEqual(bt.payment_entries[1].allocated_amount, 30)
		self.assertEqual(bt.unallocated_amount, 20)

	def test_multiple_transactions_one_payment_voucher(self):
		"""
		Test if multiple transactions fully reconcile with one payment voucher.
		"""
		pe = create_payment_entry(
			payment_type="Receive",
			party_type="Customer",
			party=self.customer,
			paid_from="Debtors - _TC",
			paid_to=self.gl_account,
			paid_amount=200,
			save=1,
			submit=1,
		)
		bt1 = create_bank_transaction(deposit=100, bank_account=self.bank_account)
		bt2 = create_bank_transaction(deposit=100, bank_account=self.bank_account)
		bulk_reconcile_vouchers(
			bt1.name,
			json.dumps([{"payment_doctype": "Payment Entry", "payment_name": pe.name}]),
		)
		bt1.reload()
		pe.reload()
		self.assertEqual(bt1.payment_entries[0].allocated_amount, 100)
		self.assertEqual(bt1.payment_entries[0].payment_entry, pe.name)
		self.assertEqual(bt1.status, "Reconciled")

		bulk_reconcile_vouchers(
			bt2.name,
			json.dumps([{"payment_doctype": "Payment Entry", "payment_name": pe.name}]),
		)
		bt2.reload()
		pe.reload()
		self.assertEqual(bt2.payment_entries[0].allocated_amount, 100)
		self.assertEqual(bt2.payment_entries[0].payment_entry, pe.name)
		self.assertEqual(bt2.status, "Reconciled")

	def test_pe_against_transaction(self):
		bt = create_bank_transaction(deposit=100, reference_no="abcdef", bank_account=self.bank_account)
		create_payment_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=self.customer,
			posting_date=bt.date,
			reference_number=bt.reference_number,
			reference_date=bt.date,
		)

		bt.reload()
		self.assertEqual(bt.payment_entries[0].allocated_amount, 100)
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.status, "Reconciled")

	@patch(
		"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_accounting_dimensions"
	)
	def test_merge_accounting_dimensions_into_payment_entry(self, mock_get_accounting_dimensions):
		mock_get_accounting_dimensions.return_value = ["test_dim"]
		payment_entry = frappe.new_doc("Payment Entry")
		payment_entry.company = "_Test Company"
		_merge_accounting_dimensions_into_payment_entry(
			payment_entry,
			json.dumps(
				{
					"test_dim": "DIM-001",
					"not_a_real_dimension": "ignored",
				}
			),
		)

		mock_get_accounting_dimensions.assert_called_once_with(as_list=True)
		self.assertEqual(payment_entry.get("test_dim"), "DIM-001")

	@patch(
		"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_accounting_dimensions"
	)
	def test_merge_accounting_dimensions_into_je_accounts(self, mock_get_accounting_dimensions):
		mock_get_accounting_dimensions.return_value = ["test_dim"]
		account_rows = [
			{"account": "Debtors - _TC"},
			{"account": "Bank - _TC", "bank_account": self.bank_account},
		]
		_merge_accounting_dimensions_into_je_accounts(
			account_rows,
			json.dumps(
				{
					"test_dim": "DIM-001",
					"not_a_real_dimension": "ignored",
				}
			),
		)

		mock_get_accounting_dimensions.assert_called_once_with(as_list=True)
		self.assertEqual(account_rows[0]["test_dim"], "DIM-001")
		self.assertEqual(account_rows[1]["test_dim"], "DIM-001")
		self.assertNotIn("not_a_real_dimension", account_rows[0])
		self.assertNotIn("not_a_real_dimension", account_rows[1])

	def test_create_journal_entry_bts_applies_accounting_dimensions_to_all_rows(self):
		project_name = frappe.db.get_value("Project", {"project_name": "_Test Bank Reco Project"}, "name")
		if not project_name:
			project_name = (
				frappe.get_doc(
					{
						"doctype": "Project",
						"project_name": "_Test Bank Reco Project",
						"company": "_Test Company",
					}
				)
				.insert()
				.name
			)

		bt = create_bank_transaction(deposit=200, reference_no="jv-dim-test", bank_account=self.bank_account)
		journal_entry = create_journal_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=self.customer,
			posting_date=bt.date,
			reference_number=bt.reference_number,
			reference_date=bt.date,
			entry_type="Bank Entry",
			second_account=frappe.db.get_value("Company", bt.company, "default_receivable_account"),
			project=project_name,
			cost_center="Main - _TC",
			allow_edit=True,
		)

		self.assertEqual(journal_entry.accounts[0].project, project_name)
		self.assertEqual(journal_entry.accounts[0].cost_center, "Main - _TC")
		self.assertEqual(journal_entry.accounts[0].credit_in_account_currency, 200)
		self.assertEqual(journal_entry.accounts[1].project, project_name)
		self.assertEqual(journal_entry.accounts[1].cost_center, "Main - _TC")
		self.assertEqual(journal_entry.accounts[1].bank_account, self.bank_account)
		self.assertEqual(journal_entry.accounts[1].debit_in_account_currency, 200)

	def test_jv_against_transaction(self):
		bt = create_bank_transaction(deposit=200, reference_no="abcdef123", bank_account=self.bank_account)
		create_journal_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=self.customer,
			posting_date=bt.date,
			reference_number=bt.reference_number,
			reference_date=bt.date,
			entry_type="Bank Entry",
			second_account=frappe.db.get_value("Company", bt.company, "default_receivable_account"),
		)

		bt.reload()
		self.assertEqual(bt.payment_entries[0].allocated_amount, 200)
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.status, "Reconciled")

	def test_unpaid_voucher_and_jv_against_transaction(self):
		"""
		Partially reconcile a bank transaction with an unpaid invoice and
		create a journal entry for the remaining amount.
		"""
		bt = create_bank_transaction(deposit=200, reference_no="abcdef123456", bank_account=self.bank_account)
		si = create_sales_invoice(
			rate=50,
			warehouse="Finished Goods - _TC",
			customer=self.customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		# 50/200 reconciled
		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)

		bt.reload()
		self.assertEqual(bt.payment_entries[0].allocated_amount, 50)
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.unallocated_amount, 150)

		# reconcile remaining 150 with a journal entry
		create_journal_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=self.customer,
			posting_date=bt.date,
			reference_number=bt.reference_number,
			reference_date=bt.date,
			entry_type="Bank Entry",
			second_account=frappe.db.get_value("Company", bt.company, "default_receivable_account"),
		)

		bt.reload()
		self.assertEqual(bt.payment_entries[1].allocated_amount, 150)
		self.assertEqual(len(bt.payment_entries), 2)
		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.unallocated_amount, 0)

	def test_unpaid_expense_claims_fully_reconcile(self):
		"""
		Test if 2 unpaid expense claims fully reconcile against a Bank Transaction.
		Test if they are paid and then the PE is reconciled.
		"""
		bt = create_bank_transaction(
			withdrawal=300, reference_no="expense-cl-001234", bank_account=self.bank_account
		)
		expense_claim = make_expense_claim(
			payable_account=frappe.db.get_value("Company", bt.company, "default_payable_account"),
			amount=200,
			sanctioned_amount=200,
			company=bt.company,
			account="Travel Expenses - _TC",
		)
		expense_claim_2 = make_expense_claim(
			payable_account=frappe.db.get_value("Company", bt.company, "default_payable_account"),
			amount=100,
			sanctioned_amount=100,
			company=bt.company,
			account="Travel Expenses - _TC",
		)
		bulk_reconcile_vouchers(
			bt.name,
			json.dumps(
				[
					{"payment_doctype": "Expense Claim", "payment_name": expense_claim.name},
					{"payment_doctype": "Expense Claim", "payment_name": expense_claim_2.name},
				]
			),
		)

		bt.reload()
		expense_claim.reload()
		expense_claim_2.reload()
		self.assertEqual(bt.payment_entries[0].allocated_amount, 300)  # one PE against 2 expense claims
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.unallocated_amount, 0)

		self.assertEqual(expense_claim.total_amount_reimbursed, 200)
		self.assertEqual(expense_claim_2.total_amount_reimbursed, 100)

		pe = get_pe_references([expense_claim.name, expense_claim_2.name])
		self.assertEqual(pe[0].allocated_amount, 200)
		self.assertEqual(pe[1].allocated_amount, 100)

	def test_invoice_and_return(self):
		"""Test invoices and returns paid by one bank transaction.

		BT: 200
		SI1, SI2, SI3: -100, -50, 350
		"""
		doc = create_bank_transaction(
			date=add_days(getdate(), -2), deposit=200, bank_account=self.bank_account
		)
		customer = create_customer()
		return_1 = create_sales_invoice(
			rate=100,
			qty=-1,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
			is_return=1,
		)
		return_2 = create_sales_invoice(
			rate=50,
			qty=-1,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
			is_return=1,
		)
		invoice_1 = create_sales_invoice(
			rate=350,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		bulk_reconcile_vouchers(
			doc.name,
			json.dumps(
				[
					{"payment_doctype": "Sales Invoice", "payment_name": return_1.name},
					{"payment_doctype": "Sales Invoice", "payment_name": return_2.name},
					{"payment_doctype": "Sales Invoice", "payment_name": invoice_1.name},
				]
			),
		)

		doc.reload()
		self.assertEqual(len(doc.payment_entries), 1)  # 1 PE made against 3 invoices
		self.assertEqual(doc.payment_entries[0].allocated_amount, 200)

		pe = get_pe_references([return_1.name, return_2.name, invoice_1.name])
		self.assertEqual(pe[0].allocated_amount, -100)
		self.assertEqual(pe[1].allocated_amount, -50)
		self.assertEqual(pe[2].allocated_amount, 350)

		# Check if the PE is posted on the same date as the BT
		self.assertEqual(
			doc.date,
			frappe.db.get_value("Payment Entry", doc.payment_entries[0].payment_entry, "posting_date"),
		)

	def test_auto_reconciliation(self):
		"""
		Test auto reconciliation between a bank transaction and a payment entry.
		"""
		day_before_yesterday = add_days(getdate(), -2)
		bt = create_bank_transaction(
			date=day_before_yesterday,
			deposit=300,
			reference_no="Test001",
			bank_account=self.bank_account,
		)
		create_payment_entry(
			payment_type="Receive",
			party_type="Customer",
			party=self.customer,
			paid_from="Debtors - _TC",
			paid_to=self.gl_account,
			paid_amount=250,
			save=1,
			submit=1,
		)

		auto_reconcile_vouchers(
			bank_account=self.bank_account,
			from_date=day_before_yesterday,
			to_date=add_days(getdate(), 1),
			filter_by_reference_date=False,
		)
		bt.reload()

		self.assertEqual(bt.payment_entries[0].allocated_amount, 250)
		self.assertEqual(bt.status, "Unreconciled")
		self.assertEqual(bt.unallocated_amount, 50)

	def test_multi_party_reconciliation(self):
		bt = create_bank_transaction(
			deposit=150,
			bank_account=self.bank_account,
			reference_no="multi-party",
			reference_date=getdate(),
		)
		customer = create_customer()
		si = create_sales_invoice(
			rate=50,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)
		si2 = create_sales_invoice(
			rate=200,
			warehouse="Finished Goods - _TC",
			customer=self.customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)
		bulk_reconcile_vouchers(
			bt.name,
			json.dumps(
				[
					{
						"payment_doctype": "Sales Invoice",
						"payment_name": si.name,
						"party": customer,
					},
					{
						"payment_doctype": "Sales Invoice",
						"payment_name": si2.name,
						"party": self.customer,
					},
				]
			),
			reconcile_multi_party=True,
		)
		bt.reload()
		si.reload()
		si2.reload()

		je = frappe.get_doc("Journal Entry", bt.payment_entries[0].payment_entry)

		self.assertEqual(len(je.accounts), 3)
		self.assertEqual(je.voucher_type, "Bank Entry")
		self.assertEqual(je.accounts[0].account, si.debit_to)
		self.assertEqual(je.accounts[0].credit, 50)
		self.assertEqual(je.accounts[0].party_type, "Customer")
		self.assertEqual(je.accounts[0].party, si.customer)
		self.assertEqual(je.accounts[0].reference_type, "Sales Invoice")
		self.assertEqual(je.accounts[0].reference_name, si.name)
		self.assertEqual(je.accounts[1].account, si2.debit_to)
		self.assertEqual(je.accounts[1].credit, 100)
		self.assertEqual(je.accounts[1].party_type, "Customer")
		self.assertEqual(je.accounts[1].party, si2.customer)
		self.assertEqual(je.accounts[1].reference_type, "Sales Invoice")
		self.assertEqual(je.accounts[1].reference_name, si2.name)
		self.assertEqual(
			je.accounts[2].account,
			frappe.db.get_value("Bank Account", bt.bank_account, "account"),
		)
		self.assertEqual(je.accounts[2].debit, 150)
		self.assertEqual(je.total_debit, 150)
		self.assertEqual(je.total_credit, 150)

		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].allocated_amount, 150)
		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.payment_entries[0].payment_document, "Journal Entry")

		self.assertEqual(si.outstanding_amount, 0)
		self.assertEqual(si2.outstanding_amount, 100)

	def test_configurable_reference_field(self):
		"""Test if configured reference field is considered."""
		settings = frappe.get_single("Banking Settings")
		settings.append("reference_fields", {"document_type": "Sales Invoice", "field_name": "custom_ref_no"})
		settings.save()

		bt = create_bank_transaction(
			date=getdate(),
			deposit=300,
			reference_no="ORD-WXL-03456",
			bank_account=self.bank_account,
			description="Payment for Order: ORD-WXL-03456 | 300 | Thank you",
		)
		si = create_sales_invoice(
			rate=300,
			warehouse="Finished Goods - _TC",
			customer=self.customer,
			cost_center="Main - _TC",
			item="Reco Item",
			do_not_submit=True,
		)
		si.custom_ref_no = "ORD-WXL-03456"
		si.submit()

		si2 = create_sales_invoice(
			rate=20,
			warehouse="Finished Goods - _TC",
			customer=self.customer,
			cost_center="Main - _TC",
			item="Reco Item",
			do_not_submit=True,
		)
		si2.custom_ref_no = "ORD-WXL-15467"
		si2.submit()

		matched_vouchers = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		first_match, second_match = matched_vouchers[0], matched_vouchers[1]

		# Get linked payments and check if the custom field value is present
		self.assertEqual(len(matched_vouchers), 2)
		self.assertEqual(first_match["reference_no"], si.custom_ref_no)
		self.assertEqual(first_match["name"], si.name)
		self.assertEqual(first_match["rank"], 6)
		self.assertEqual(first_match["ref_in_desc_match"], 1)
		self.assertEqual(first_match["reference_number_match"], 1)
		self.assertEqual(second_match["ref_in_desc_match"], 0)
		self.assertEqual(second_match["reference_number_match"], 0)
		#  Check if ranking across another SI is correct
		self.assertEqual(second_match["reference_no"], si2.custom_ref_no)
		self.assertEqual(second_match["name"], si2.name)
		self.assertEqual(second_match["rank"], 3)
		self.assertEqual(second_match["ref_in_desc_match"], 0)

	def test_no_configurable_reference_field(self):
		"""Test if Name is considered as the reference field if not configured."""
		bt = create_bank_transaction(
			date=getdate(),
			deposit=300,
			reference_no="Test001",
			bank_account=self.bank_account,
			description="Payment for Order: ORD-WXL-03456 | 300 | Thank you",
		)
		si = create_sales_invoice(
			rate=300,
			warehouse="Finished Goods - _TC",
			customer=self.customer,
			cost_center="Main - _TC",
			item="Reco Item",
			do_not_submit=True,
		)
		si.custom_ref_no = "ORD-WXL-03456"
		si.submit()

		matched_vouchers = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		first_match = matched_vouchers[0]

		# Get linked payments and check if the custom field value is present
		self.assertEqual(len(matched_vouchers), 1)
		self.assertEqual(first_match["reference_no"], si.name)
		self.assertEqual(first_match["name"], si.name)
		self.assertEqual(first_match["rank"], 4)
		self.assertEqual(first_match["amount_match"], 1)
		self.assertEqual(first_match["ref_in_desc_match"], 0)

	def test_split_jv_match_against_transaction(self):
		"""
		Test if a split JV shows up as a single consolidated row in the tool
		and fully reconciles the Bank Transaction.
		"""
		bt = create_bank_transaction(deposit=200, reference_no="abcdef123", bank_account=self.bank_account)
		journal_entry = create_journal_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=self.customer,
			posting_date=bt.date,
			reference_number=bt.reference_number,
			reference_date=bt.date,
			entry_type="Bank Entry",
			second_account=frappe.db.get_value("Company", bt.company, "default_receivable_account"),
			allow_edit=True,
		)

		# Split the JV Row into two
		journal_entry.accounts[1].debit_in_account_currency = 100
		journal_entry.append(
			"accounts",
			{
				"account": frappe.get_value("Bank Account", bt.bank_account, "account"),
				"bank_account": bt.bank_account,
				"credit_in_account_currency": 0.0,
				"debit_in_account_currency": 100,
				"cost_center": journal_entry.accounts[1].cost_center,
			},
		)
		journal_entry.submit()

		matched_vouchers = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["journal_entry"],
			from_date=getdate(),
			to_date=getdate(),
		)
		first_match = matched_vouchers[0]

		self.assertEqual(len(matched_vouchers), 1)
		self.assertEqual(first_match["reference_no"], bt.reference_number)
		self.assertEqual(first_match["name"], journal_entry.name)
		self.assertEqual(first_match["paid_amount"], 200.0)

	def test_unreconcile_reoffers_fee_journal_entry(self):
		"""Withdrawal fee JEs must be offered again once unreconciled from the BT."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		bank = create_bank("Citi Bank Fee Reoffer", swift_number="CITIUS36")
		gl_account = create_bank_gl_account("_Test Fee Reoffer Bank - _TC")
		fee_account = create_bank_gl_account("_Test Fee Reoffer Offset - _TC")
		bank_account = frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "Fee Reoffer Account",
				"bank": bank.name,
				"account": gl_account,
				"bank_fee_account": fee_account,
				"company": "_Test Company",
				"is_company_account": 1,
			}
		).insert()

		bt = frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"company": "_Test Company",
				"description": "Withdrawal with auto-generated fee entry",
				"date": getdate(),
				"withdrawal": 5.0,
				"included_fee": 1.0,
				"currency": "INR",
				"bank_account": bank_account.name,
				"reference_number": "FEE-FILTER-002",
			}
		).insert()
		bt.submit()
		bt.reload()

		self.assertEqual(len(bt.payment_entries), 1)
		fee_journal_entry = frappe.get_doc("Journal Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(str(fee_journal_entry.clearance_date), str(bt.date))

		bt.remove_payment_entries()
		bt.reload()
		fee_journal_entry.reload()

		self.assertEqual(bt.status, "Unreconciled")
		self.assertFalse(bt.payment_entries)
		self.assertIsNone(fee_journal_entry.clearance_date)

		matched_vouchers = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["journal_entry"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		matched_names = [voucher["name"] for voucher in matched_vouchers]

		self.assertIn(fee_journal_entry.name, matched_names)
		self.assertEqual(matched_vouchers[0]["paid_amount"], 1.0)

	def test_cheque_number_linked_journal_entry_is_excluded_from_matches(self):
		"""Cheque-number-linked custom JEs must stay hidden."""
		bt = create_bank_transaction(
			date=getdate(),
			withdrawal=200,
			bank_account=self.bank_account,
			reference_no="CUSTOM-JE-001",
		)
		journal_entry = create_journal_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=self.customer,
			posting_date=bt.date,
			reference_number=bt.name,
			reference_date=bt.date,
			entry_type="Bank Entry",
			second_account=frappe.db.get_value("Company", bt.company, "default_receivable_account"),
			allow_edit=True,
		)
		journal_entry.submit()

		self.assertFalse(journal_entry.is_system_generated)
		self.assertFalse(
			frappe.db.exists(
				"Journal Entry Account",
				{
					"parent": journal_entry.name,
					"reference_type": "Bank Transaction",
					"reference_name": bt.name,
				},
			)
		)

		matched_vouchers = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["journal_entry"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		matched_names = [voucher["name"] for voucher in matched_vouchers]

		self.assertNotIn(journal_entry.name, matched_names)

	def test_usd_purchase_invoice_paid_in_usd(self):
		"""Reconcile a USD Purchase Invoice via a USD bank account.

		Invoice: 100 USD, payable account in company currency (INR).
		Bank Transaction: 100 USD withdrawal.
		Expected: invoice fetched with 100 USD outstanding (converted from 8000 INR),
		multi-currency PE with paid_amount=100 USD, full reconciliation.
		"""
		_gl_account, usd_bank_account = setup_usd_bank()
		supplier = create_supplier("USD Supplier Inc.", "USD")
		create_currency_exchange("USD", "INR", 80)

		pi = make_purchase_invoice(
			supplier=supplier,
			currency="USD",
			conversion_rate=80,
			rate=100,
			qty=1,
			cost_center="_Test Cost Center - _TC",
		)

		bt = create_bank_transaction(
			withdrawal=100,
			bank_account=usd_bank_account,
			currency="USD",
		)

		# Verify the invoice is fetched with the correct outstanding and currency
		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["purchase_invoice", "unpaid_invoices"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		pi_match = next(m for m in matched if m["name"] == pi.name)
		self.assertEqual(pi_match["paid_amount"], 100)  # converted from 8000 INR
		self.assertEqual(pi_match["currency"], "USD")

		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Purchase Invoice", "payment_name": pi.name}]),
		)

		bt.reload()
		pi.reload()

		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.unallocated_amount, 0)
		self.assertEqual(pi.outstanding_amount, 0)

		pe = frappe.get_doc("Payment Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(pe.paid_amount, 100)
		self.assertEqual(pe.paid_from_account_currency, "USD")
		self.assertEqual(pe.paid_to_account_currency, "INR")

	def test_usd_purchase_invoice_paid_in_company_currency(self):
		"""Reconcile a USD Purchase Invoice via an INR bank account.

		Invoice: 100 USD (= 8000 INR outstanding), payable account in INR.
		Bank Transaction: 8000 INR withdrawal.
		Expected: invoice fetched with 8000 INR outstanding (unchanged),
		same-currency PE with paid_amount=8000 INR, full reconciliation.
		"""
		supplier = create_supplier("USD Supplier Inc.", "USD")

		pi = make_purchase_invoice(
			supplier=supplier,
			currency="USD",
			conversion_rate=80,
			rate=100,
			qty=1,
			cost_center="_Test Cost Center - _TC",
		)

		bt = create_bank_transaction(
			withdrawal=8000,
			bank_account=self.bank_account,
		)

		# Verify the invoice is fetched with unchanged INR outstanding
		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["purchase_invoice", "unpaid_invoices"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		pi_match = next(m for m in matched if m["name"] == pi.name)
		self.assertEqual(pi_match["paid_amount"], 8000)  # INR, unchanged
		self.assertEqual(pi_match["currency"], "INR")

		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Purchase Invoice", "payment_name": pi.name}]),
		)

		bt.reload()
		pi.reload()

		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.unallocated_amount, 0)
		self.assertEqual(pi.outstanding_amount, 0)

		pe = frappe.get_doc("Payment Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(pe.paid_amount, 8000)
		self.assertEqual(pe.paid_from_account_currency, "INR")
		self.assertEqual(pe.paid_to_account_currency, "INR")

	def test_usd_sales_invoice_paid_in_usd(self):
		"""Reconcile a USD Sales Invoice via a USD bank account.

		Invoice: 100 USD, receivable account in company currency (INR).
		Bank Transaction: 100 USD deposit.
		Expected: invoice fetched with 100 USD outstanding (converted from 8000 INR),
		multi-currency PE with received_amount=100 USD, full reconciliation.
		"""
		_gl_account, usd_bank_account = setup_usd_bank()
		customer = create_customer("USD Client Inc.", "USD")
		create_currency_exchange("USD", "INR", 80)

		si = create_sales_invoice(
			customer=customer,
			currency="USD",
			conversion_rate=80,
			rate=100,
			warehouse="Finished Goods - _TC",
			cost_center="Main - _TC",
			item="Reco Item",
		)

		bt = create_bank_transaction(
			deposit=100,
			bank_account=usd_bank_account,
			currency="USD",
		)

		# Verify the invoice is fetched with the correct outstanding and currency
		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		si_match = next(m for m in matched if m["name"] == si.name)
		self.assertEqual(si_match["paid_amount"], 100)  # converted from 8000 INR
		self.assertEqual(si_match["currency"], "USD")

		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)

		bt.reload()
		si.reload()

		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.unallocated_amount, 0)
		self.assertEqual(si.outstanding_amount, 0)

		pe = frappe.get_doc("Payment Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(pe.received_amount, 100)
		self.assertEqual(pe.paid_from_account_currency, "INR")
		self.assertEqual(pe.paid_to_account_currency, "USD")

	def test_usd_sales_invoice_paid_in_inr_with_fee(self):
		"""Company-currency bank fees can be represented as PE deductions."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		fee_gl_account = create_bank_gl_account("_Test INR Bank Fee USD Invoice GL")
		fee_expense_account = create_bank_gl_account("_Test INR Bank Fee USD Invoice Expense")
		bank_account_with_fee = create_bank_account(
			gl_account=fee_gl_account,
			bank_account_name="INR Account With USD Invoice Fee",
			bank_fee_account=fee_expense_account,
		)
		customer = create_customer("USD Invoice Fee Client", "USD")

		si = create_sales_invoice(
			customer=customer,
			currency="USD",
			conversion_rate=80,
			rate=100,
			warehouse="Finished Goods - _TC",
			cost_center="Main - _TC",
			item="Reco Item",
		)
		bt = create_bank_transaction(
			deposit=7987,
			included_fee=13,
			bank_account=bank_account_with_fee,
		)

		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices", "exact_match"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		si_match = next(m for m in matched if m["name"] == si.name)
		self.assertEqual(si_match["paid_amount"], 8000)
		self.assertEqual(si_match["currency"], "INR")

		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)

		bt.reload()
		si.reload()
		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.unallocated_amount, 0)
		self.assertEqual(si.outstanding_amount, 0)
		self.assertEqual(bt.payment_entries[0].payment_document, "Payment Entry")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 7987)

		pe = frappe.get_doc("Payment Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(pe.paid_amount, 7987)
		self.assertEqual(pe.received_amount, 7987)
		self.assertEqual(pe.difference_amount, 0)

		fee_deductions = [row for row in pe.deductions if row.account == fee_expense_account]
		self.assertEqual(len(fee_deductions), 1)
		self.assertEqual(fee_deductions[0].amount, 13)
		self.assertFalse(fee_deductions[0].is_exchange_gain_loss)

	def test_rejects_foreign_fee(self):
		"""PE deductions are company-currency only, but this BT fee is in USD."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		bank = create_bank("Citi Bank USD Fee", swift_number="CITIUS37")
		gl_account = create_bank_gl_account("_Test USD Bank Fee Reco", "USD")
		fee_account = create_bank_gl_account("_Test USD Bank Fee Expense Reco", "USD")
		usd_bank_account = create_bank_account(
			bank.name,
			gl_account,
			"USD Reco Fee Account",
			bank_fee_account=fee_account,
		)
		customer = create_customer("USD Fee Client Inc.", "USD")
		create_currency_exchange("USD", "INR", 90)

		si = create_sales_invoice(
			customer=customer,
			currency="USD",
			conversion_rate=80,
			rate=113,
			warehouse="Finished Goods - _TC",
			cost_center="Main - _TC",
			item="Reco Item",
		)
		bt = create_bank_transaction(
			deposit=100,
			included_fee=13,
			bank_account=usd_bank_account,
			currency="USD",
		)

		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices", "exact_match"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		si_match = next(m for m in matched if m["name"] == si.name)
		self.assertEqual(si_match["paid_amount"], 113)

		frappe.db.savepoint("before_multicurrency_included_fee_reconcile")
		with self.assertRaises(CurrencyMismatchError):
			bulk_reconcile_vouchers(
				bt.name,
				json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
			)
		frappe.db.rollback(save_point="before_multicurrency_included_fee_reconcile")

		bt.reload()
		si.reload()

		self.assertFalse(bt.payment_entries)
		self.assertEqual(bt.unallocated_amount, 100)
		self.assertEqual(si.outstanding_amount, 9040)

	def test_usd_sales_invoice_paid_in_company_currency(self):
		"""Reconcile a USD Sales Invoice via an INR bank account.

		Invoice: 100 USD (= 8000 INR outstanding), receivable account in INR.
		Bank Transaction: 8000 INR deposit.
		Expected: invoice fetched with 8000 INR outstanding (unchanged),
		same-currency PE with paid_amount=8000 INR, full reconciliation.
		"""
		customer = create_customer("USD Client Inc.", "USD")

		si = create_sales_invoice(
			customer=customer,
			currency="USD",
			conversion_rate=80,
			rate=100,
			warehouse="Finished Goods - _TC",
			cost_center="Main - _TC",
			item="Reco Item",
		)

		bt = create_bank_transaction(
			deposit=8000,
			bank_account=self.bank_account,
		)

		# Verify the invoice is fetched with unchanged INR outstanding
		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		si_match = next(m for m in matched if m["name"] == si.name)
		self.assertEqual(si_match["paid_amount"], 8000)  # INR, unchanged
		self.assertEqual(si_match["currency"], "INR")

		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)

		bt.reload()
		si.reload()

		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.unallocated_amount, 0)
		self.assertEqual(si.outstanding_amount, 0)

		pe = frappe.get_doc("Payment Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(pe.paid_amount, 8000)
		self.assertEqual(pe.paid_from_account_currency, "INR")
		self.assertEqual(pe.paid_to_account_currency, "INR")

	def test_usd_jv_against_eur_company(self):
		"""Test if the tool can create a USD Journal Entry against a EUR company."""
		bank = create_bank("Citi Bank USD", swift_number="CITIUS34")
		gl_account = create_bank_gl_account("_Test USD Bank Reco Tool", "USD")
		usd_receivable_account = frappe.get_doc(
			{
				"doctype": "Account",
				"company": "_Test Company",
				"parent_account": "Accounts Receivable - _TC",
				"account_type": "Receivable",
				"is_group": 0,
				"account_name": "USD Receivable - _TC",
				"account_currency": "USD",
			}
		).insert()
		bank_account = create_bank_account(bank.name, gl_account, "USD Account")
		customer = create_customer(customer_name="USD Inc.", currency="USD")

		bt = create_bank_transaction(
			date=getdate(),
			deposit=200,
			reference_no="usd-jv-001",
			bank_account=bank_account,
			currency="USD",
			description="USD Inc.",
		)

		create_journal_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=customer,
			posting_date=bt.date,
			reference_number=bt.reference_number,
			reference_date=bt.date,
			entry_type="Bank Entry",
			second_account=usd_receivable_account.name,
		)

		bt.reload()
		self.assertEqual(bt.payment_entries[0].payment_document, "Journal Entry")

		journal_entry = frappe.get_doc("Journal Entry", bt.payment_entries[0].payment_entry)

		self.assertTrue(journal_entry.multi_currency)
		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].allocated_amount, 200)

	def test_included_fee_deposit_creates_jv_with_fee_row(self):
		"""Reconciling a deposit with included_fee must create a JE that settles
		the full invoice amount (deposit + fee) and books the fee to the bank fee account.

		BT: deposit=75, included_fee=5
		SI: 80
		Expected JE: Dr Bank 75, Dr Bank Fees 5, Cr Receivable 80
		"""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		fee_gl_account = create_bank_gl_account("_Test Bank Fee Reco GL")
		fee_expense_account = create_bank_gl_account("_Test Bank Fee Reco Expense")
		bank_account_with_fee = create_bank_account(
			gl_account=fee_gl_account,
			bank_account_name="Personal Account With Fee",
			bank_fee_account=fee_expense_account,
		)

		bt = create_bank_transaction(
			deposit=75,
			included_fee=5,
			bank_account=bank_account_with_fee,
		)
		customer = create_customer()
		si = create_sales_invoice(
			rate=80,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices", "exact_match"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		si_match = next(m for m in matched if m["name"] == si.name)
		self.assertEqual(si_match["paid_amount"], 80)

		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)

		bt.reload()
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].payment_document, "Journal Entry")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 75)
		self.assertEqual(bt.status, "Reconciled")

		je = frappe.get_doc("Journal Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(je.docstatus, 1)

		accounts = {}
		for row in je.accounts:
			accounts[row.account] = row

		# Bank debited for deposit amount only
		self.assertEqual(accounts[fee_gl_account].debit_in_account_currency, 75)
		# Fee account debited for the included fee
		self.assertEqual(accounts[fee_expense_account].debit_in_account_currency, 5)

		si.reload()
		self.assertEqual(si.outstanding_amount, 0)

	def test_included_fee_deposit_rejects_partial_reconciliation(self):
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		fee_gl_account = create_bank_gl_account("_Test Bank Fee Partial GL")
		fee_expense_account = create_bank_gl_account("_Test Bank Fee Partial Expense")
		bank_account_with_fee = create_bank_account(
			gl_account=fee_gl_account,
			bank_account_name="Personal Account With Partial Fee",
			bank_fee_account=fee_expense_account,
		)

		bt = create_bank_transaction(
			deposit=110,
			included_fee=13,
			bank_account=bank_account_with_fee,
		)
		customer = create_customer("Fee Partial Customer")
		si = create_sales_invoice(
			rate=120,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		with self.assertRaises(FullReconciliationRequiredError):
			bulk_reconcile_vouchers(
				bt.name,
				json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
			)

		bt.reload()
		si.reload()
		self.assertFalse(bt.payment_entries)
		self.assertEqual(bt.unallocated_amount, 110)
		self.assertEqual(si.outstanding_amount, 120)

	def test_included_fee_deposit_rejects_followup_reconciliation(self):
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 1)

		fee_gl_account = create_bank_gl_account("_Test Bank Fee Followup GL")
		fee_expense_account = create_bank_gl_account("_Test Bank Fee Followup Expense")
		bank_account_with_fee = create_bank_account(
			gl_account=fee_gl_account,
			bank_account_name="Personal Account With Followup Fee",
			bank_fee_account=fee_expense_account,
		)

		bt = create_bank_transaction(
			deposit=110,
			included_fee=13,
			bank_account=bank_account_with_fee,
		)
		customer = create_customer("Fee Followup Customer")
		si = create_sales_invoice(
			rate=120,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)
		si2 = create_sales_invoice(
			rate=120,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		bt.append(
			"payment_entries",
			{
				"payment_document": "Sales Invoice",
				"payment_entry": si.name,
				"allocated_amount": 107,
			},
		)
		bt.allocated_amount = 107
		bt.unallocated_amount = 3
		bt.save()

		with self.assertRaises(FullReconciliationRequiredError):
			bulk_reconcile_vouchers(
				bt.name,
				json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si2.name}]),
			)

		si2.reload()
		self.assertEqual(si2.outstanding_amount, 120)

	def test_included_fee_deposit_ignores_fee_when_disabled(self):
		"""With the global feature flag disabled, deposit-side included fees must
		not affect exact matching or reconciliation."""
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)

		fee_gl_account = create_bank_gl_account("_Test Bank Fee Disabled GL")
		fee_expense_account = create_bank_gl_account("_Test Bank Fee Disabled Expense")
		bank_account_with_fee = create_bank_account(
			gl_account=fee_gl_account,
			bank_account_name="Personal Account With Disabled Fee Flag",
			bank_fee_account=fee_expense_account,
		)

		bt = create_bank_transaction(
			deposit=75,
			included_fee=5,
			bank_account=bank_account_with_fee,
		)
		customer = create_customer("Fee Flag Disabled Customer")
		si = create_sales_invoice(
			rate=75,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)
		si_with_fee = create_sales_invoice(
			rate=80,
			warehouse="Finished Goods - _TC",
			customer=customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		matched = get_linked_payments(
			bank_transaction_name=bt.name,
			document_types=["sales_invoice", "unpaid_invoices", "exact_match"],
			from_date=add_days(getdate(), -1),
			to_date=add_days(getdate(), 1),
		)
		matched_names = [voucher["name"] for voucher in matched]
		self.assertIn(si.name, matched_names)
		self.assertNotIn(si_with_fee.name, matched_names)

		bulk_reconcile_vouchers(
			bt.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)

		bt.reload()
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.payment_entries[0].payment_document, "Payment Entry")
		self.assertEqual(bt.payment_entries[0].allocated_amount, 75)
		self.assertEqual(bt.status, "Reconciled")

		pe = frappe.get_doc("Payment Entry", bt.payment_entries[0].payment_entry)
		self.assertEqual(pe.docstatus, 1)
		self.assertFalse(pe.deductions)

		si.reload()
		si_with_fee.reload()
		self.assertEqual(si.outstanding_amount, 0)
		self.assertEqual(si_with_fee.outstanding_amount, 80)


def get_pe_references(vouchers: list):
	return frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_name": ["in", vouchers]},
		fields=["parent", "reference_name", "allocated_amount", "outstanding_amount"],
		order_by="idx",
	)


def create_bank_transaction(
	date: str | None = None,
	deposit: float | None = None,
	withdrawal: float | None = None,
	reference_no: str | None = None,
	reference_date: str | None = None,
	bank_account: str | None = None,
	description: str | None = None,
	currency: str = "INR",
	included_fee: float | None = None,
):
	values = {
		"doctype": "Bank Transaction",
		"company": "_Test Company",
		"description": description or "1512567 BG/000002918 OPSKATTUZWXXX AT776000000098709837 Herr G",
		"date": date or frappe.utils.nowdate(),
		"deposit": deposit or 0.0,
		"withdrawal": withdrawal or 0.0,
		"currency": currency,
		"bank_account": bank_account,
		"reference_number": reference_no,
	}
	if included_fee is not None:
		values["included_fee"] = included_fee

	doc = frappe.get_doc(values).insert()
	return doc.submit()


def create_customer(customer_name="_Test Customer", currency=None):
	if not frappe.db.exists("Customer", customer_name):
		customer = frappe.new_doc("Customer")
		customer.customer_name = customer_name
		customer.type = "Individual"
		customer.customer_group = "Commercial"
		customer.territory = "All Territories"

		if currency:
			customer.default_currency = currency
		customer.save()
		customer = customer.name
	else:
		customer = customer_name

	return customer


def create_bank_account(
	bank_name="Citi Bank",
	gl_account="_Test Bank - _TC",
	bank_account_name="Personal Account",
	company=None,
	bank_fee_account=None,
) -> str:
	if bank_account := frappe.db.exists(
		"Bank Account",
		{
			"account_name": bank_account_name,
			"bank": bank_name,
			"account": gl_account,
			"company": company or "_Test Company",
			"is_company_account": 1,
		},
	):
		if bank_fee_account:
			frappe.db.set_value("Bank Account", bank_account, "bank_fee_account", bank_fee_account)
		return bank_account

	values = {
		"doctype": "Bank Account",
		"account_name": bank_account_name,
		"bank": bank_name,
		"account": gl_account,
		"company": company or "_Test Company",
		"is_company_account": 1,
	}
	if bank_fee_account:
		values["bank_fee_account"] = bank_fee_account

	bank_account = frappe.get_doc(values).insert()
	return bank_account.name


def create_bank(bank_name: str = "Citi Bank", swift_number: str = "CITIUS33"):
	if not frappe.db.exists("Bank", bank_name):
		bank = frappe.new_doc("Bank")
		bank.bank_name = bank_name
		bank.swift_number = swift_number
		bank.insert()
	else:
		bank = frappe.get_doc("Bank", bank_name)
	return bank


def create_bank_gl_account(account_name: str = "_Test Bank - _TC", currency: str = "INR") -> str:
	gl_account = frappe.get_doc(
		{
			"doctype": "Account",
			"company": "_Test Company",
			"parent_account": "Current Assets - _TC",
			"account_type": "Bank",
			"is_group": 0,
			"account_name": account_name,
			"account_currency": currency,
		}
	).insert()
	return gl_account.name


def create_supplier(supplier_name="_Test Supplier", currency=None):
	if not frappe.db.exists("Supplier", supplier_name):
		supplier = frappe.new_doc("Supplier")
		supplier.supplier_name = supplier_name
		supplier.supplier_group = "All Supplier Groups"
		supplier.supplier_type = "Individual"
		if currency:
			supplier.default_currency = currency
		supplier.save()
	return supplier_name


def setup_usd_bank():
	"""Create a USD bank account for multi-currency tests."""
	bank = create_bank("Citi Bank USD", swift_number="CITIUS34")
	gl_account = create_bank_gl_account("_Test USD Bank Reco Beta", "USD")
	bank_account = create_bank_account(bank.name, gl_account, "USD Reco Account")
	return gl_account, bank_account


def create_currency_exchange(from_currency, to_currency, rate, date=None):
	frappe.get_doc(
		{
			"doctype": "Currency Exchange",
			"from_currency": from_currency,
			"to_currency": to_currency,
			"exchange_rate": rate,
			"date": date or frappe.utils.nowdate(),
			"for_buying": 1,
			"for_selling": 1,
		}
	).insert()
