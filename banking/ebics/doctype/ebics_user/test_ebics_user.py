# Copyright (c) 2024, ALYF GmbH and Contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

# The tests create their own Bank
test_ignore = ["Bank", "Country"]


class TestEBICSUser(FrappeTestCase):
	def setUp(self):
		if not frappe.db.exists("Bank", "_Test EBICS Bank"):
			bank = frappe.new_doc("Bank")
			bank.bank_name = "_Test EBICS Bank"
			bank.ebics_host_id = "TESTHOST"
			bank.ebics_url = "https://ebics.example.com/ebics"
			bank.insert()

		# Not inserted, so that the user does not get registered with the license backend
		self.ebics_user = frappe.get_doc(
			{"doctype": "EBICS User", "bank": "_Test EBICS Bank", "protocol_version": "H004"}
		)
		frappe.clear_messages()

	@patch(
		"banking.ebics.doctype.ebics_user.ebics_user.get_protocol_versions",
		side_effect=Exception("Connection refused"),
	)
	def test_warn_when_bank_does_not_answer_hev(self, _):
		self.ebics_user.validate()

		messages = frappe.get_message_log()
		self.assertEqual(len(messages), 1)
		self.assertIn("EBICS URL", messages[0]["message"])

	@patch(
		"banking.ebics.doctype.ebics_user.ebics_user.get_protocol_versions",
		return_value={"H005": "03.00"},
	)
	def test_unsupported_protocol_version(self, _):
		self.assertRaises(frappe.ValidationError, self.ebics_user.validate)

	@patch(
		"banking.ebics.doctype.ebics_user.ebics_user.get_protocol_versions",
		return_value={"H004": "02.50", "H005": "03.00"},
	)
	def test_supported_protocol_version(self, _):
		self.ebics_user.validate()

		self.assertEqual(frappe.get_message_log(), [])
