# Copyright (c) 2024, ALYF GmbH and Contributors
# See license.txt
import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.password import set_encrypted_password
from requests import Response

from banking.connectors.admin_request import AdminRequest

REGISTER = "banking_admin.ebics_api.register_ebics_user"
REMOVE = "banking_admin.ebics_api.remove_ebics_user"
HOST_ID = "_TESTHOST"

# The tests create their own Bank. ERPNext's Bank test records need more setup.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Bank"]


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


class TestEBICSUser(IntegrationTestCase):
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

	def test_bank_host_id_is_locked_while_used(self):
		bank = frappe.get_doc("Bank", create_ebics_bank("_Test EBICS Bank Locked"))
		bank.ebics_host_id = "_OTHERHOST"
		bank.save()  # no EBICS User links to this bank yet

		with mock_admin_backend():
			new_ebics_user(bank.name, "PARTNER9", "USER9").insert()

		bank.ebics_host_id = HOST_ID
		with self.assertRaises(frappe.ValidationError):
			bank.save()
