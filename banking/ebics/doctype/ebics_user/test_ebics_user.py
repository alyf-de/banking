# Copyright (c) 2024, ALYF GmbH and Contributors
# See license.txt
from io import BytesIO
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.file_lock import LockTimeoutError
from frappe.utils.synchronization import filelock
from pypdf import PdfWriter

from banking.ebics.doctype.ebics_user.ebics_user import download_bank_keys, initialize
from banking.ebics.utils import register_fintech

EBICS_USER_MODULE = "banking.ebics.doctype.ebics_user.ebics_user"

# The tests create their own Bank. They do not need the test records of ERPNext.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Bank"]


class TestEBICSUser(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_single_value("Banking Settings", {"enabled": 1, "enable_ebics": 1})
		cls.user = create_ebics_user()

	def setUp(self):
		self.user.db_set({"initialized": 0, "ini_sent": 0})
		self.manager = MagicMock()
		self.manager.create_ini_letter.return_value = make_pdf()

	def call(self, method, **kwargs):
		with (
			patch(f"{EBICS_USER_MODULE}.get_ebics_manager", return_value=self.manager),
			patch.object(frappe.db, "commit"),
		):
			return method(ebics_user=self.user.name, **kwargs)

	def initialize(self):
		self.call(initialize, passphrase="secret", signature_passphrase="secret", store_passphrase=0)

	def test_retry_after_failed_hia_does_not_send_ini_again(self):
		self.manager.send_authentication_keys.side_effect = ConnectionError("HIA failed")
		self.assertRaises(ConnectionError, self.initialize)
		self.assertEqual(self.manager.send_signature_key.call_count, 1)

		self.manager.send_authentication_keys.side_effect = None
		self.initialize()

		self.assertEqual(self.manager.send_signature_key.call_count, 1)
		self.assertEqual(self.manager.send_authentication_keys.call_count, 2)
		self.user.reload()
		self.assertTrue(self.user.initialized)

	def test_retry_after_failed_ini_sends_ini_again(self):
		self.manager.send_signature_key.side_effect = ConnectionError("INI failed")
		self.assertRaises(ConnectionError, self.initialize)

		self.manager.send_signature_key.side_effect = None
		self.initialize()

		self.assertEqual(self.manager.send_signature_key.call_count, 2)
		self.assertEqual(self.manager.send_authentication_keys.call_count, 1)

	def test_second_initialization_at_the_same_time_fails(self):
		with filelock(f"initialize_ebics_user_{self.user.name}", timeout=0):
			self.assertRaises(LockTimeoutError, self.initialize)

		self.manager.create_user_keys.assert_not_called()
		self.manager.send_signature_key.assert_not_called()

	def test_known_ebics_error_explains_what_to_check(self):
		error = get_ebics_technical_error()
		self.manager.send_signature_key.side_effect = error(error.EBICS_USER_UNKNOWN)

		with self.assertRaises(frappe.ValidationError) as context:
			self.initialize()

		self.assertIn("Partner ID", str(context.exception))
		self.assertIn("EBICS_USER_UNKNOWN", str(context.exception))

	def test_unknown_ebics_error_is_raised_unchanged(self):
		error = get_ebics_technical_error()
		self.manager.download_bank_keys.side_effect = error(error.EBICS_TX_ABORT)

		self.assertRaises(error, self.call, download_bank_keys)


def make_pdf() -> bytes:
	writer = PdfWriter()
	writer.add_blank_page(width=100, height=100)
	pdf = BytesIO()
	writer.write(pdf)
	return pdf.getvalue()


def get_ebics_technical_error():
	register_fintech()
	from fintech.ebics import EbicsTechnicalError

	return EbicsTechnicalError


def create_ebics_user():
	bank = frappe.get_doc(
		{
			"doctype": "Bank",
			"bank_name": "_Test EBICS Initialize Bank",
			"ebics_host_id": "TESTHOST",
			"ebics_url": "https://ebics.example.com",
		}
	).insert()

	# Registration with the license backend and the protocol check talk to external services.
	with (
		patch("banking.connectors.admin_request.requests.request"),
		patch(f"{EBICS_USER_MODULE}.get_protocol_versions", return_value={}),
	):
		return frappe.get_doc(
			{
				"doctype": "EBICS User",
				"full_name": "Test User",
				"bank": bank.name,
				"partner_id": "TESTPARTNER",
				"user_id": "TESTUSER",
				"protocol_version": "H004",
			}
		).insert()
