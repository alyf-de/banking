# Copyright (c) 2023, ALYF GmbH and Contributors
# See license.txt
import json

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.test.accounts_mixin import AccountsTestMixin

from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
	reconcile_vouchers,
)
from erpnext.accounts.doctype.bank_transaction.test_bank_transaction import (
	create_bank_account,
	create_gl_account,
)
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import (
	create_sales_invoice,
)


class TestBankReconciliationToolBeta(AccountsTestMixin, FrappeTestCase):
	def setUp(self):
		uniq_identifier = frappe.generate_hash(length=10)
		gl_account = create_gl_account(f"_Test Bank {uniq_identifier}")
		create_bank_account(gl_account=gl_account)

		self.create_item(
			item_name="Reco Item", company="_Test Company", warehouse="Finished Goods - _TC"
		)

	def test_unpaid_invoice_more_than_transaction(self):
		"""
		Test unpaid invoices fully reconcile.
		BT: 150
		SI1, SI2: 100, 100 (200) (partial: 150)
		"""
		doc = create_bank_transaction(withdrawal=150)
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

	def test_unpaid_invoice_less_than_transaction(self):
		"""
		Test if unpaid invoices partially reconcile.
		BT: 100
		SI1, SI2: 50, 20 (70)
		"""
		doc = create_bank_transaction(withdrawal=100)
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


def get_pe_references(vouchers: list):
	return frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_name": ["in", vouchers]},
		fields=["reference_name", "allocated_amount", "outstanding_amount"],
		order_by="idx",
	)


def create_bank_transaction(
	date: str = None, deposit: float = None, withdrawal: float = None
):
	doc = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"description": "1512567 BG/000002918 OPSKATTUZWXXX AT776000000098709837 Herr G",
			"date": date or frappe.utils.nowdate(),
			"deposit": deposit or 0.0,
			"withdrawal": withdrawal or 0.0,
			"currency": "INR",
			"bank_account": "Checking Account - Citi Bank",
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
