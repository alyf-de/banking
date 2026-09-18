# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, today

from banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.test_bank_reconciliation_tool_beta import (
	create_bank,
	create_bank_account,
	create_bank_gl_account,
	create_supplier,
)

COMPANY_IBAN = "DE02120300000000202051"
SUPPLIER_IBAN = "DE02100500000054540402"


class TestSEPAPaymentOrder(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		create_bank("SEPA Test Bank", swift_number="DEUTDEFF")
		gl_account = create_bank_gl_account("_Test SEPA Bank")
		cls.bank_account = create_bank_account(
			bank_name="SEPA Test Bank", gl_account=gl_account, bank_account_name="SEPA Test Account"
		)
		frappe.db.set_value("Bank Account", cls.bank_account, "iban", COMPANY_IBAN)

		cls.supplier = create_supplier("_Test SEPA Supplier")
		if not frappe.db.exists("Bank Account", {"party_type": "Supplier", "party": cls.supplier}):
			frappe.get_doc(
				{
					"doctype": "Bank Account",
					"account_name": "SEPA Supplier Account",
					"bank": "SEPA Test Bank",
					"party_type": "Supplier",
					"party": cls.supplier,
					"iban": SUPPLIER_IBAN,
					"is_default": 1,
				}
			).insert()

	def new_payment_order(self, execution_date: str):
		return frappe.new_doc(
			"SEPA Payment Order",
			company="_Test Company",
			bank_account=self.bank_account,
			iban=COMPANY_IBAN,
			execution_date=execution_date,
		)

	def make_invoice(self, due_date: str, discount_date: str | None = None):
		"""Submit a Purchase Invoice with a single payment schedule row."""
		invoice = make_purchase_invoice(
			supplier=self.supplier,
			qty=1,
			rate=100,
			do_not_submit=True,
			bill_no=frappe.generate_hash(length=8),
		)
		# ERPNext creates the payment schedule on insert, we only adjust its dates
		schedule = invoice.payment_schedule[0]
		schedule.due_date = due_date
		schedule.discount_date = discount_date
		schedule.discount_type = "Percentage"
		schedule.discount = 2 if discount_date else 0
		invoice.submit()
		return invoice

	def test_fetch_payables_by_due_date(self):
		due = self.make_invoice(due_date=add_days(today(), 5)).name
		not_due = self.make_invoice(due_date=add_days(today(), 30)).name

		order = self.new_payment_order(execution_date=today())
		order.fetch_payables(add_days(today(), 10))

		fetched = [payment.reference_name for payment in order.payments]
		self.assertIn(due, fetched)
		self.assertNotIn(not_due, fetched)

		# fetching again must not duplicate rows
		order.fetch_payables(add_days(today(), 10))
		self.assertEqual(len(order.payments), len(fetched))

	def test_fetch_payables_uses_discounted_amount(self):
		invoice = self.make_invoice(due_date=add_days(today(), 30), discount_date=add_days(today(), 5))

		# paying within the discount period: 2 % less
		order = self.new_payment_order(execution_date=add_days(today(), 3))
		order.fetch_payables(add_days(today(), 5))
		payment = next(p for p in order.payments if p.reference_name == invoice.name)
		self.assertEqual(payment.amount, flt(invoice.grand_total * 0.98, 2))
		self.assertEqual(payment.iban, SUPPLIER_IBAN)

		# paying after the discount expired: full amount
		late_order = self.new_payment_order(execution_date=add_days(today(), 10))
		late_order.fetch_payables(add_days(today(), 5))
		late_payment = next(p for p in late_order.payments if p.reference_name == invoice.name)
		self.assertEqual(late_payment.amount, invoice.grand_total)
