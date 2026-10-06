# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from erpnext.accounts.doctype.purchase_invoice.test_purchase_invoice import make_purchase_invoice
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, today

from banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.test_bank_reconciliation_tool_beta import (
	create_bank,
	create_bank_account,
	create_bank_gl_account,
	create_supplier,
)
from banking.testing_utils import create_mode_of_payment

COMPANY_IBAN = "DE02120300000000202051"
SUPPLIER_IBAN = "DE02100500000054540402"
NON_EEA_IBAN = "CH9300762011623852957"
OTHER_NON_EEA_IBAN = "GB29NWBK60161331926819"


class TestSEPAPaymentOrder(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		create_bank("SEPA Test Bank", swift_number="DEUTDEFF")
		gl_account = create_bank_gl_account("_Test SEPA Bank")
		cls.bank_account = create_bank_account(
			bank_name="SEPA Test Bank", gl_account=gl_account, bank_account_name="SEPA Test Account"
		)
		frappe.db.set_value("Bank Account", cls.bank_account, "iban", COMPANY_IBAN)

		create_bank("SEPA Supplier Bank", swift_number="BELADEBEXXX")
		cls.supplier = create_supplier("_Test SEPA Supplier")
		if not frappe.db.exists("Bank Account", {"party_type": "Supplier", "party": cls.supplier}):
			frappe.get_doc(
				{
					"doctype": "Bank Account",
					"account_name": "SEPA Supplier Account",
					"bank": "SEPA Supplier Bank",
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

	def make_invoice(
		self, due_date: str, discount_date: str | None = None, mode_of_payment: str | None = None
	):
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
		schedule.mode_of_payment = mode_of_payment
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

	def test_fetch_payables_skips_inaccessible_documents(self):
		"""A document the user may not read must not abort the whole fetch."""
		blocked = self.make_invoice(due_date=add_days(today(), 5)).name
		readable = self.make_invoice(due_date=add_days(today(), 5)).name

		from banking.custom.purchase_invoice import make_sepa_payment_order as invoice_to_order

		def raise_for_blocked(source_name, *args, **kwargs):
			if source_name == blocked:
				raise frappe.PermissionError
			return invoice_to_order(source_name, *args, **kwargs)

		order = self.new_payment_order(execution_date=today())
		with patch("banking.custom.purchase_invoice.make_sepa_payment_order", side_effect=raise_for_blocked):
			order.fetch_payables(add_days(today(), 10))

		fetched = [payment.reference_name for payment in order.payments]
		self.assertIn(readable, fetched)
		self.assertNotIn(blocked, fetched)

	def test_fetch_payables_ignores_old_payables(self):
		"""Invoices posted before Ignore Payables Before are not fetched."""
		invoice = self.make_invoice(due_date=add_days(today(), 5)).name

		def fetch():
			order = self.new_payment_order(execution_date=today())
			order.fetch_payables(add_days(today(), 10))
			return [payment.reference_name for payment in order.payments]

		frappe.db.set_single_value("Banking Settings", "ignore_payables_before", add_days(today(), 1))
		self.assertNotIn(invoice, fetch())

		frappe.db.set_single_value("Banking Settings", "ignore_payables_before", today())
		self.assertIn(invoice, fetch())

	def test_fetch_payables_by_mode_of_payment(self):
		"""Only the exact Mode of Payment qualifies. Without one, only rows without one qualify."""
		own_account = frappe.db.get_value("Bank Account", self.bank_account, "account")
		transfer = create_mode_of_payment("_Test SEPA Transfer", own_account)
		# Same account, but not paid by SEPA Payment Order
		draft = create_mode_of_payment("_Test SEPA Draft", own_account)

		by_transfer = self.make_invoice(due_date=add_days(today(), 5), mode_of_payment=transfer).name
		by_draft = self.make_invoice(due_date=add_days(today(), 5), mode_of_payment=draft).name
		no_mode = self.make_invoice(due_date=add_days(today(), 5)).name

		def fetch(mode_of_payment=None):
			order = self.new_payment_order(execution_date=today())
			order.fetch_payables(add_days(today(), 10), mode_of_payment)
			return [payment.reference_name for payment in order.payments]

		fetched = fetch(transfer)
		self.assertIn(by_transfer, fetched)
		self.assertNotIn(by_draft, fetched)
		self.assertNotIn(no_mode, fetched)

		fetched = fetch()
		self.assertIn(no_mode, fetched)
		self.assertNotIn(by_transfer, fetched)
		self.assertNotIn(by_draft, fetched)

	def test_fetch_payables_rejects_mode_of_other_account(self):
		other_account = create_bank_gl_account("_Test SEPA Other Bank")
		other_mode = create_mode_of_payment("_Test SEPA Other Transfer", other_account)

		order = self.new_payment_order(execution_date=today())
		with self.assertRaises(frappe.ValidationError):
			order.fetch_payables(add_days(today(), 10), other_mode)

	def add_payment(self, order, iban: str, swift_number: str):
		order.append(
			"payments",
			{
				"recipient": "_Test SEPA Recipient",
				"purpose": "Test",
				"iban": iban,
				"swift_number": swift_number,
				"amount": 100,
				"currency": "EUR",
				"charges": "SHAR",
			},
		)

	def test_eea_payment_has_no_bic(self):
		"""EEA payments are IBAN-only, so a BIC of another branch cannot break the order."""
		order = self.new_payment_order(execution_date=today())
		self.add_payment(order, SUPPLIER_IBAN, swift_number="DEUTDEFF")

		order.run_method("before_validate")

		# Stored BIC is kept, in case the payment later needs it
		self.assertEqual(order.payments[0].swift_number, "DEUTDEFF")
		order.verify_xml_render()

	def test_bic_mismatch_names_row(self):
		order = self.new_payment_order(execution_date=today())
		self.add_payment(order, SUPPLIER_IBAN, swift_number=None)
		self.add_payment(order, NON_EEA_IBAN, swift_number="DEUTDEFF")
		self.add_payment(order, OTHER_NON_EEA_IBAN, swift_number="DEUTDEFF")

		order.run_method("before_validate")

		with self.assertRaisesRegex(
			frappe.ValidationError,
			f"Row 2: BIC DEUTDEFF .*{NON_EEA_IBAN}.*Row 3: BIC DEUTDEFF .*{OTHER_NON_EEA_IBAN}",
		):
			order.verify_xml_render()

	def test_non_eea_debtor_keeps_bic(self):
		"""IBAN-only applies only when debtor and creditor are in the EEA."""
		order = self.new_payment_order(execution_date=today())
		order.iban = NON_EEA_IBAN
		self.add_payment(order, SUPPLIER_IBAN, swift_number="BELADEBEXXX")

		order.run_method("before_validate")

		self.assertEqual(order.payments[0].swift_number, "BELADEBEXXX")
