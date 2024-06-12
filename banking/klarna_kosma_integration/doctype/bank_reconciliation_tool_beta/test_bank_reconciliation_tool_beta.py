# Copyright (c) 2023, ALYF GmbH and Contributors
# See license.txt
import json

import frappe
from frappe.utils import add_days, getdate
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.test.accounts_mixin import AccountsTestMixin

from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
	reconcile_vouchers,
)
from erpnext.accounts.doctype.bank_transaction.test_bank_transaction import (
	create_gl_account,
)
from erpnext.accounts.doctype.payment_entry.test_payment_entry import (
	create_payment_entry,
)
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import (
	create_sales_invoice,
)

from banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta import (
	create_journal_entry_bts,
	create_payment_entry_bts,
)

from hrms.hr.doctype.expense_claim.test_expense_claim import make_expense_claim


class TestBankReconciliationToolBeta(AccountsTestMixin, FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_bank()
		cls.gl_account = create_gl_account("_Test Bank Reco Tool")
		cls.bank_account = create_bank_account(gl_account=cls.gl_account)
		cls.customer = create_customer(customer_name="ABC Inc.")

		cls.create_item(
			cls, item_name="Reco Item", company="_Test Company", warehouse="Finished Goods - _TC"
		)

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

		reconcile_vouchers(
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
			frappe.db.get_value(
				"Payment Entry", doc.payment_entries[0].payment_entry, "posting_date"
			),
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

		reconcile_vouchers(
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
		reconcile_vouchers(
			bt1.name,
			json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]),
		)
		bt1.reload()
		si.reload()
		self.assertEqual(bt1.payment_entries[0].allocated_amount, 100)
		self.assertEqual(si.outstanding_amount, 100)

		reconcile_vouchers(
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
		reconcile_vouchers(
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
		reconcile_vouchers(
			bt1.name,
			json.dumps([{"payment_doctype": "Payment Entry", "payment_name": pe.name}]),
		)
		bt1.reload()
		pe.reload()
		self.assertEqual(bt1.payment_entries[0].allocated_amount, 100)
		self.assertEqual(bt1.payment_entries[0].payment_entry, pe.name)
		self.assertEqual(bt1.status, "Reconciled")

		reconcile_vouchers(
			bt2.name,
			json.dumps([{"payment_doctype": "Payment Entry", "payment_name": pe.name}]),
		)
		bt2.reload()
		pe.reload()
		self.assertEqual(bt2.payment_entries[0].allocated_amount, 100)
		self.assertEqual(bt2.payment_entries[0].payment_entry, pe.name)
		self.assertEqual(bt2.status, "Reconciled")

	def test_pe_against_transaction(self):
		bt = create_bank_transaction(
			deposit=100, reference_no="abcdef", bank_account=self.bank_account
		)
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

	def test_jv_against_transaction(self):
		bt = create_bank_transaction(
			deposit=200, reference_no="abcdef123", bank_account=self.bank_account
		)
		create_journal_entry_bts(
			bank_transaction_name=bt.name,
			party_type="Customer",
			party=self.customer,
			posting_date=bt.date,
			reference_number=bt.reference_number,
			reference_date=bt.date,
			entry_type="Bank Entry",
			second_account=frappe.db.get_value(
				"Company", bt.company, "default_receivable_account"
			),
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
		bt = create_bank_transaction(
			deposit=200, reference_no="abcdef123456", bank_account=self.bank_account
		)
		si = create_sales_invoice(
			rate=50,
			warehouse="Finished Goods - _TC",
			customer=self.customer,
			cost_center="Main - _TC",
			item="Reco Item",
		)

		# 50/200 reconciled
		reconcile_vouchers(
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
			second_account=frappe.db.get_value(
				"Company", bt.company, "default_receivable_account"
			),
		)

		bt.reload()
		self.assertEqual(bt.payment_entries[1].allocated_amount, 150)
		self.assertEqual(len(bt.payment_entries), 2)
		self.assertEqual(bt.status, "Reconciled")
		self.assertEqual(bt.unallocated_amount, 0)

	def test_unpaid_expense_claim_fully_reconcile(self):
		bt = create_bank_transaction(
			withdrawal=200, reference_no="expense-cl-001234", bank_account=self.bank_account
		)
		expense_claim = make_expense_claim(
			payable_account=frappe.db.get_value(
				"Company", bt.company, "default_payable_account"
			),
			amount=300,
			sanctioned_amount=200,
			company=bt.company,
			account="Travel Expenses - _TC",
		)
		reconcile_vouchers(
			bt.name,
			json.dumps(
				[{"payment_doctype": "Expense Claim", "payment_name": expense_claim.name}]
			),
		)

		bt.reload()
		expense_claim.reload()
		self.assertEqual(bt.payment_entries[0].allocated_amount, 200)
		self.assertEqual(len(bt.payment_entries), 1)
		self.assertEqual(bt.unallocated_amount, 0)
		self.assertEqual(expense_claim.total_amount_reimbursed, 200)
		self.assertEqual(expense_claim.total_claimed_amount, 300)


def get_pe_references(vouchers: list):
	return frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_name": ["in", vouchers]},
		fields=["parent", "reference_name", "allocated_amount", "outstanding_amount"],
		order_by="idx",
	)


def create_bank_transaction(
	date: str = None,
	deposit: float = None,
	withdrawal: float = None,
	reference_no: str = None,
	reference_date: str = None,
	bank_account: str = None,
):
	doc = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"company": "_Test Company",
			"description": "1512567 BG/000002918 OPSKATTUZWXXX AT776000000098709837 Herr G",
			"date": date or frappe.utils.nowdate(),
			"deposit": deposit or 0.0,
			"withdrawal": withdrawal or 0.0,
			"currency": "INR",
			"bank_account": bank_account,
			"reference_number": reference_no,
		}
	).insert()
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
		return bank_account

	bank_account = frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": bank_account_name,
			"bank": bank_name,
			"account": gl_account,
			"company": company or "_Test Company",
			"is_company_account": 1,
		}
	).insert()
	return bank_account.name


def create_bank(bank_name="Citi Bank"):
	if not frappe.db.exists("Bank", bank_name):
		bank = frappe.new_doc("Bank")
		bank.bank_name = bank_name
		bank.swift_number = "CITIUS33"
		bank.insert()
	else:
		bank = frappe.get_doc("Bank", bank_name)
	return bank
