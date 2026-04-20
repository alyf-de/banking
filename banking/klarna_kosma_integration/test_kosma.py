import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)
from frappe.tests.utils import FrappeTestCase

from banking.klarna_kosma_integration.admin import Admin


class TestKosma(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		doc = frappe.get_single("Banking Settings")
		doc.enabled = True
		doc.api_token = "xabsttcpQr5"
		doc.customer_id = "ADCB8A"
		doc.admin_endpoint = "http://banking-admin:8000"
		doc.save()

		default_bank_account = frappe.db.get_value("Company", "_Test Company", "default_bank_account")
		if default_bank_account is None:
			frappe.db.set_value(
				"Company",
				"_Test Company",
				"default_bank_account",
				get_default_bank_cash_account("_Test Company", "Cash").get("account"),
			)

		return super().setUpClass()

	@classmethod
	def tearDownClass(cls):
		doc = frappe.get_single("Banking Settings")
		doc.enabled = False
		doc.save()

	def test_admin_obj(self):
		"""Test if Admin objects are initialised correctly"""
		admin = Admin()
		self.assertEqual(admin.api_token, "xabsttcpQr5")
		self.assertEqual(admin.customer_id, "ADCB8A")
