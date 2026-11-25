# Copyright (c) 2024, ALYF GmbH and Contributors
# See license.txt
import json
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import MagicMock, patch

import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase
=======
from frappe.tests import IntegrationTestCase
from frappe.utils.file_lock import LockTimeoutError
>>>>>>> 5518947 (fix(EBICS User): keep keys after a failed initialization and explain EBICS errors (#499))
from frappe.utils.password import set_encrypted_password
from frappe.utils.synchronization import filelock
from pypdf import PdfWriter
from requests import Response

from banking.connectors.admin_request import AdminRequest
from banking.ebics.doctype.ebics_user.ebics_user import download_bank_keys, initialize
from banking.ebics.utils import register_fintech

EBICS_USER_MODULE = "banking.ebics.doctype.ebics_user.ebics_user"
REGISTER = "banking_admin.ebics_api.register_ebics_user"
REMOVE = "banking_admin.ebics_api.remove_ebics_user"
HOST_ID = "_TESTHOST"
KEYRING = '{"keys": "created by the first try"}'

# The tests create their own Bank. ERPNext's Bank test records need more setup.
test_ignore = ["Bank", "Country"]


def make_response(status_code: int, message: str | None = None) -> Response:
	response = Response()
	response.status_code = status_code
	response._content = json.dumps({"message": message}).encode() if message else b""
	return response


def mock_admin_backend(*responses: Response):
	"""Patch the HTTP call to the license backend. Without responses, every call returns 204."""
	return patch.object(
		AdminRequest, "request", side_effect=responses or None, return_value=make_response(204)
	)


def get_calls(mock) -> list[tuple]:
	"""Return (endpoint, partner_id, user_id) for each call to the license backend."""
	return [(c.args[1], c.args[2]["partner_id"], c.args[2]["user_id"]) for c in mock.call_args_list]


def get_host_calls(mock) -> list[tuple]:
	"""Return (endpoint, host_id, partner_id) for each call to the license backend."""
	return [(c.args[1], c.args[2]["host_id"], c.args[2]["partner_id"]) for c in mock.call_args_list]


def create_ebics_bank(bank_name: str = "_Test EBICS Bank") -> str:
	if not frappe.db.exists("Bank", bank_name):
		bank = frappe.new_doc("Bank")
		bank.bank_name = bank_name
		bank.ebics_host_id = HOST_ID
		# Nothing listens on this port, so the lookup of protocol versions fails fast.
		bank.ebics_url = "http://127.0.0.1:9/ebics"
		bank.insert()
	return bank_name


def new_ebics_user(bank: str, partner_id: str, user_id: str, **kwargs):
	user = frappe.new_doc("EBICS User")
	user.bank = bank
	user.partner_id = partner_id
	user.user_id = user_id
	user.update(kwargs)
	return user


class TestEBICSUser(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_single_value(
			"Banking Settings",
			{"admin_endpoint": "https://admin.example.com", "customer_id": "_test_customer"},
		)
		set_encrypted_password("Banking Settings", "Banking Settings", "_test_token", "api_token")
		cls.bank = create_ebics_bank()

	def test_insert_registers_once(self):
		with mock_admin_backend() as backend:
			new_ebics_user(self.bank, "PARTNER1", "USER1").insert()

		self.assertEqual(get_calls(backend), [(REGISTER, "PARTNER1", "USER1")])

	def test_invalid_insert_does_not_register(self):
		user = new_ebics_user(self.bank, "PARTNER2", "USER2", protocol_version="H005", needs_certificates=0)
		with mock_admin_backend() as backend, self.assertRaises(frappe.ValidationError):
			user.insert()

		self.assertEqual(get_calls(backend), [])

	def test_changed_ids_remove_old_registration(self):
		with mock_admin_backend():
			user = new_ebics_user(self.bank, "PARTNER3X", "USER3").insert()

		user.partner_id = "PARTNER3"
		with mock_admin_backend() as backend:
			user.save()

		self.assertEqual(
			get_calls(backend),
			[(REMOVE, "PARTNER3X", "USER3"), (REGISTER, "PARTNER3", "USER3")],
		)

	def test_failed_registration_of_changed_ids_restores_old_registration(self):
		with mock_admin_backend():
			user = new_ebics_user(self.bank, "PARTNER11X", "USER11").insert()

		user.partner_id = "PARTNER11"
		with (
			mock_admin_backend(
				make_response(204), make_response(429, "Too many requests"), make_response(204)
			) as backend,
			self.assertRaisesRegex(frappe.ValidationError, "Too many requests"),
		):
			user.save()

		self.assertEqual(
			get_calls(backend),
			[
				(REMOVE, "PARTNER11X", "USER11"),
				(REGISTER, "PARTNER11", "USER11"),
				(REGISTER, "PARTNER11X", "USER11"),
			],
		)

	def test_unchanged_ids_keep_registration(self):
		with mock_admin_backend():
			user = new_ebics_user(self.bank, "PARTNER4", "USER4").insert()

		user.intraday_sync = 1
		with mock_admin_backend() as backend:
			user.save()

		self.assertEqual(get_calls(backend), [(REGISTER, "PARTNER4", "USER4")])

	def test_ids_are_stripped(self):
		with mock_admin_backend() as backend:
			user = new_ebics_user(self.bank, " PARTNER5 ", "USER5 ").insert()

		self.assertEqual((user.partner_id, user.user_id), ("PARTNER5", "USER5"))
		self.assertEqual(get_calls(backend), [(REGISTER, "PARTNER5", "USER5")])

	def test_incomplete_ids_are_not_registered(self):
		"""Bank, Partner ID and User ID are optional, so a draft can be saved without them."""
		with mock_admin_backend() as backend:
			user = new_ebics_user(self.bank, "PARTNER10", None).insert()
			user.delete()

		self.assertEqual(get_calls(backend), [])

	def test_registration_error_shows_backend_message(self):
		for status_code in (402, 403, 417, 429, 500):
			message = f"Backend error {status_code}"
			user = new_ebics_user(self.bank, f"PARTNER6{status_code}", "USER6")
			with (
				mock_admin_backend(make_response(status_code, message)),
				self.assertRaisesRegex(frappe.ValidationError, message),
			):
				user.insert()

	def test_registration_error_without_message_shows_status_code(self):
		user = new_ebics_user(self.bank, "PARTNER7", "USER7")
		with mock_admin_backend(make_response(502)), self.assertRaisesRegex(frappe.ValidationError, "502"):
			user.insert()

	def test_trash_removes_registration(self):
		with mock_admin_backend():
			user = new_ebics_user(self.bank, "PARTNER8", "USER8").insert()

		with mock_admin_backend() as backend:
			user.delete()

		self.assertEqual(get_calls(backend), [(REMOVE, "PARTNER8", "USER8")])

	def test_new_bank_host_id_moves_registrations(self):
		bank = frappe.get_doc("Bank", create_ebics_bank("_Test EBICS Bank Move"))
		with mock_admin_backend():
			new_ebics_user(bank.name, "PARTNER9", "USER9").insert()

		bank.ebics_host_id = "_NEWHOST"
		with mock_admin_backend() as backend:
			bank.save()

		self.assertEqual(
			get_host_calls(backend),
			[(REMOVE, HOST_ID, "PARTNER9"), (REGISTER, "_NEWHOST", "PARTNER9")],
		)

	def test_failed_move_restores_old_bank_host_id_registrations(self):
		bank = frappe.get_doc("Bank", create_ebics_bank("_Test EBICS Bank Move Failure"))
		with mock_admin_backend():
			new_ebics_user(bank.name, "PARTNER12", "USER12").insert()
			new_ebics_user(bank.name, "PARTNER13", "USER13").insert()

		# Same order as the move
		first, second = frappe.get_all("EBICS User", filters={"bank": bank.name}, pluck="partner_id")
		bank.ebics_host_id = "_NEWHOST"
		ok = make_response(204)
		with (
			mock_admin_backend(ok, ok, ok, make_response(429, "Too many requests"), ok, ok, ok) as backend,
			self.assertRaisesRegex(frappe.ValidationError, "Too many requests"),
		):
			bank.save()

		self.assertEqual(
			get_host_calls(backend),
			[
				(REMOVE, HOST_ID, first),
				(REGISTER, "_NEWHOST", first),
				(REMOVE, HOST_ID, second),
				(REGISTER, "_NEWHOST", second),
				(REGISTER, HOST_ID, second),
				(REMOVE, "_NEWHOST", first),
				(REGISTER, HOST_ID, first),
			],
		)

	def test_bank_host_id_is_locked_after_initialization(self):
		bank = frappe.get_doc("Bank", create_ebics_bank("_Test EBICS Bank Locked"))
		with mock_admin_backend():
			user = new_ebics_user(bank.name, "PARTNER14", "USER14").insert()
		user.db_set("initialized", 1)

		bank.ebics_host_id = "_NEWHOST"
		with mock_admin_backend() as backend, self.assertRaises(frappe.ValidationError):
			bank.save()

		self.assertEqual(get_calls(backend), [])


<<<<<<< HEAD
class TestValidateBank(FrappeTestCase):
=======
class TestInitializeEBICSUser(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_single_value("Banking Settings", {"enabled": 1, "enable_ebics": 1})
		# Usually `get_ebics_manager` registers fintech, but the tests mock it.
		register_fintech()
		cls.user = create_ebics_user()

	def setUp(self):
		self.user.db_set({"initialized": 0, "ini_sent": 0, "keyring": None, "partner_id": "TESTPARTNER"})
		frappe.db.set_value("Bank", self.user.bank, "ebics_host_id", "TESTHOST")
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

	def test_changed_ids_send_ini_again(self):
		self.manager.send_authentication_keys.side_effect = ConnectionError("HIA failed")
		self.assertRaises(ConnectionError, self.initialize)

		self.user.reload()
		self.user.partner_id = "OTHERPARTNER"
		with mock_external_services():
			self.user.save()

		self.manager.send_authentication_keys.side_effect = None
		self.initialize()

		self.assertEqual(self.manager.send_signature_key.call_count, 2)

	def test_changed_bank_host_id_sends_ini_again(self):
		self.manager.send_authentication_keys.side_effect = ConnectionError("HIA failed")
		self.assertRaises(ConnectionError, self.initialize)

		bank = frappe.get_doc("Bank", self.user.bank)
		bank.ebics_host_id = "OTHERHOST"
		with mock_admin_backend():
			bank.save()

		self.manager.send_authentication_keys.side_effect = None
		self.initialize()

		self.assertEqual(self.manager.send_signature_key.call_count, 2)

	def test_wrong_passphrase_explains_to_use_the_first_one(self):
		for ini_sent in (0, 1):
			self.user.db_set("ini_sent", ini_sent)
			# Message of fintech when the keyring cannot decrypt the stored keys
			with (
				patch(
					f"{EBICS_USER_MODULE}.get_ebics_manager",
					side_effect=ValueError("key #USER.E002 corrupted or wrong passphrase"),
				),
				self.assertRaisesRegex(frappe.ValidationError, "same passphrases") as context,
			):
				initialize(self.user.name, "other secret", "other secret", store_passphrase=0)

			self.assertEqual("reset the user" in str(context.exception), bool(ini_sent))

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
	with (
		mock_admin_backend(),
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
>>>>>>> 5518947 (fix(EBICS User): keep keys after a failed initialization and explain EBICS errors (#499))
	def setUp(self):
		# Not inserted, so that the user does not get registered with the license backend
		self.ebics_user = frappe.get_doc(
			{"doctype": "EBICS User", "bank": create_ebics_bank(), "protocol_version": "H004"}
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
