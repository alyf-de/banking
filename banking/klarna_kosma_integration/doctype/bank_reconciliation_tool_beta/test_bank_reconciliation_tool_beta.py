# Copyright (c) 2023, ALYF GmbH and Contributors
# See license.txt

# import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.test.accounts_mixin import AccountsTestMixin

# from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import reconcile_vouchers
# from erpnext.accounts.doctype.bank_transaction.test_bank_transaction import create_bank_account
# from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice


class TestBankReconciliationToolBeta(AccountsTestMixin, FrappeTestCase):
	pass


# def setUp(self):
# 	create_bank_account()

# def test_unpaid_invoice_more_than_transaction(self):
# 	"""
# 	Test if an unpaid invoice is partially allocated when it's outstanding amount
# 	is more than the transaction's unallocated amount
# 	"""
# 	doc = frappe.get_doc(
# 	{
# 		"doctype": "Bank Transaction",
# 		"description": "1512567 BG/000002918 OPSKATTUZWXXX AT776000000098709837 Herr G",
# 		"date": frappe.utils.nowdate(),
# 		"deposit": 50,
# 		"currency": "INR",
# 		"bank_account": "Checking Account - Citi Bank",
# 	}
# 	).insert()
# 	doc.submit()

# 	self.create_customer()
# 	si = create_sales_invoice(rate=20, warehouse="Finished Goods - _TC", customer=self.customer)
# 	si2 = create_sales_invoice(rate=40, warehouse="Finished Goods - _TC", customer=self.customer)

# 	reconcile_vouchers(
# 		doc.name,
# 		[
# 			{"payment_doctype": "Sales Invoice", "payment_name": si.name},
# 			{"payment_doctype": "Sales Invoice", "payment_name": si2.name},
# 		]
# 	)

# 	doc.reload()
# 	si.reload()
# 	si2.reload()

# 	self.assertEqual(doc.payment_entries[0].allocated_amount, 20)
# 	self.assertEqual(doc.payment_entries[1].allocated_amount, 30)

# 	pe = frappe.get_all(
# 		"Payment Entry Reference",
# 		filters={"reference_name": ["in", [si.name, si2.name]]},
# 		fields=["reference_name", "allocated_amount", "grand_total", "outstanding_amount"]
# 	)

# 	self.assertEqual(pe[0].allocated_amount, 20)
