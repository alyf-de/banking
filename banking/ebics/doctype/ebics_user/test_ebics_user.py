# Copyright (c) 2024, ALYF GmbH and Contributors
# See license.txt
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.file_lock import LockTimeoutError
from frappe.utils.password import set_encrypted_password
from frappe.utils.synchronization import filelock
from pypdf import PdfWriter
from requests import Response

from banking.connectors.admin_request import AdminRequest
from banking.ebics.doctype.ebics_user.ebics_user import download_bank_keys, initialize
from banking.ebics.utils import register_fintech

EBICS_USER_MODULE = "banking.ebics.doctype.ebics_user.ebics_user"

# The tests create their own Bank. They do not need the test records of ERPNext.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Bank", "Country"]

KEYRING = '{"keys": "created by the first try"}'


class TestEBICSUser(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_single_value("Banking Settings", {"enabled": 1, "enable_ebics": 1})
		# Usually `get_ebics_manager` registers fintech, but the tests mock it.
		register_fintech()
		cls.user = create_ebics_user()

	def setUp(self):
		self.user.db_set({"initialized": 0, "ini_sent": 0, "keyring": None})
		self.manager = MagicMock()
		self.manager.create_user_keys.side_effect = self.store_keys
		self.manager.create_ini_letter.return_value = make_pdf()

	def store_keys(self):
		frappe.db.set_value("EBICS User", self.user.name, "keyring", KEYRING)

	def call(self, method, **kwargs):
		"""Call `method` like a request: if it fails, roll back to the last commit."""
		frappe.db.savepoint("last_commit")
		with (
			patch(f"{EBICS_USER_MODULE}.get_ebics_manager", return_value=self.manager),
			patch.object(frappe.db, "commit", side_effect=lambda: frappe.db.savepoint("last_commit")),
		):
			try:
				return method(ebics_user=self.user.name, **kwargs)
			except Exception:
				frappe.db.rollback(save_point="last_commit")
				raise

	def initialize(self):
		self.call(initialize, passphrase="secret", signature_passphrase="secret", store_passphrase=0)

	def test_retry_after_failed_hia_does_not_send_ini_again(self):
		self.manager.send_authentication_keys.side_effect = ConnectionError("HIA failed")
		self.assertRaises(ConnectionError, self.initialize)
		self.assertEqual(self.manager.send_signature_key.call_count, 1)
		self.user.reload()
		self.assertTrue(self.user.ini_sent)
		self.assertEqual(self.user.keyring, KEYRING)

		self.manager.send_authentication_keys.side_effect = None
		self.initialize()

		self.assertEqual(self.manager.send_signature_key.call_count, 1)
		self.assertEqual(self.manager.send_authentication_keys.call_count, 2)
		self.user.reload()
		self.assertTrue(self.user.initialized)

	def test_retry_after_failed_ini_sends_ini_again(self):
		self.manager.send_signature_key.side_effect = ConnectionError("INI failed")
		self.assertRaises(ConnectionError, self.initialize)
		self.user.reload()
		self.assertFalse(self.user.ini_sent)
		self.assertEqual(self.user.keyring, KEYRING)

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


@contextmanager
def mock_external_services():
	"""Registration with the license backend and the protocol check talk to external services."""
	set_encrypted_password("Banking Settings", "Banking Settings", "_test_token", "api_token")
	registered = Response()
	registered.status_code = 204
	with (
		patch.object(AdminRequest, "request", return_value=registered),
		patch(f"{EBICS_USER_MODULE}.get_protocol_versions", return_value={}),
	):
		yield


def create_ebics_user():
	bank = frappe.get_doc(
		{
			"doctype": "Bank",
			"bank_name": "_Test EBICS Initialize Bank",
			"ebics_host_id": "TESTHOST",
			"ebics_url": "https://ebics.example.com",
		}
	).insert()

	with mock_external_services():
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


class TestValidateBank(IntegrationTestCase):
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
