# Copyright (c) 2022, ALYF GmbH and Contributors
# See license.txt

import json
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase
=======
from frappe.tests import IntegrationTestCase
from frappe.utils.password import set_encrypted_password
>>>>>>> 63d1b54 (feat(Banking Settings): show and remove unmatched EBICS registrations (#498))

from banking.klarna_kosma_integration.doctype.banking_settings.banking_settings import (
	get_unmatched_ebics_registrations,
	remove_ebics_registration,
	successful_request_exists,
)
from banking.testing_utils import (
	create_bank_account,
	create_currency_account,
	get_bank_parent_account,
	set_automatic_bank_fee_entries,
)


class TestBankingSettings(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_automatic_bank_fee_entries(False)

		parent_account = get_bank_parent_account()
		cls.account_without_fee = create_currency_account(
			"EUR", parent_account, "_Test_Banking_Settings_Account_No_Fee"
		)
		cls.bank_account_without_fee = create_bank_account(
			cls.account_without_fee.name, "_Test_Banking_Settings_Bank_Account_No_Fee"
		)

	def setUp(self):
		super().setUp()
		set_automatic_bank_fee_entries(False)

	def tearDown(self):
		set_automatic_bank_fee_entries(False)
		super().tearDown()

	def test_successful_request_exists(self):
		with create_successful_request("C53", date(2025, 1, 1), date(2025, 1, 1)) as request:
			self.assertTrue(successful_request_exists(None, request.order_type, date(2025, 1, 1)))
			self.assertFalse(successful_request_exists(None, request.order_type, date(2025, 1, 2)))

	def test_requires_fee_accounts_when_enabling_fee_entries(
		self,
	):
		settings = frappe.get_single("Banking Settings")
		settings.enable_automatic_journal_entries_for_bank_fees = 1

		with self.assertRaises(frappe.ValidationError):
			settings.save()

		self.assertEqual(
			frappe.db.get_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees"),
			0,
		)

	def test_successful_request_exists_checks_all_matching_requests(self):
		with create_successful_request("C53", date(2025, 1, 2), date(2025, 1, 2)):
			with create_successful_request("C53", date(2025, 1, 1), date(2025, 1, 1)):
				self.assertTrue(successful_request_exists(None, "C53", date(2025, 1, 1)))

	def test_successful_request_exists_ignores_malformed_dates(self):
		valid_parameters = json.dumps({"start_date": "2025-01-01", "end_date": "2025-01-01"})
		for malformed_parameters in (
			{"start_date": "not-a-date", "end_date": "2025-01-01"},
			{"start_date": "2025-01-01", "end_date": "not-a-date"},
		):
			with self.subTest(parameters=malformed_parameters):
				with patch(
					"banking.klarna_kosma_integration.doctype.banking_settings.banking_settings.frappe.get_all",
					return_value=[
						SimpleNamespace(parameters=json.dumps(malformed_parameters)),
						SimpleNamespace(parameters=valid_parameters),
					],
				):
					self.assertTrue(successful_request_exists(None, "C53", date(2025, 1, 1)))


class TestUnmatchedEBICSRegistrations(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_encrypted_password("Banking Settings", "Banking Settings", "test-token", "api_token")

		if not frappe.db.exists("Bank", "_Test EBICS Registration Bank"):
			frappe.get_doc(
				{"doctype": "Bank", "bank_name": "_Test EBICS Registration Bank", "ebics_host_id": "testhost"}
			).insert()

		# Insert without hooks to skip the bank connection check and the registration request.
		frappe.get_doc(
			{
				"doctype": "EBICS User",
				"name": "_Test EBICS Registration User",
				"bank": "_Test EBICS Registration Bank",
				"partner_id": "partner1",
				"user_id": "user1",
			}
		).db_insert()

	def test_returns_registrations_without_local_ebics_user(self):
		backend_registrations = [
			{"host_id": "TESTHOST", "partner_id": "PARTNER1", "user_id": "USER1"},
			{"host_id": "TESTHOST", "partner_id": "PARTNER1", "user_id": "USER2"},
			{"host_id": "OTHERHOST", "partner_id": "PARTNER1", "user_id": "USER1"},
		]

		with patch_admin_request(backend_registrations):
			unmatched = get_unmatched_ebics_registrations()

		self.assertEqual(unmatched, backend_registrations[1:])

	def test_remove_unmatched_registration(self):
		with patch_admin_request() as request:
			remove_ebics_registration("TESTHOST", "PARTNER1", "USER2")

		request.assert_called_once()
		self.assertEqual(request.call_args.kwargs["method"], "POST")
		self.assertTrue(request.call_args.kwargs["url"].endswith("banking_admin.ebics_api.remove_ebics_user"))
		self.assertEqual(
			request.call_args.kwargs["json"],
			{"host_id": "TESTHOST", "partner_id": "PARTNER1", "user_id": "USER2"},
		)

	def test_remove_refuses_registration_of_local_ebics_user(self):
		with patch_admin_request() as request:
			with self.assertRaises(frappe.ValidationError):
				remove_ebics_registration("TESTHOST", "PARTNER1", "USER1")

		request.assert_not_called()


def patch_admin_request(message=None):
	"""Replace the HTTP request to the admin backend with a successful response."""
	response = Mock()
	response.json.return_value = {"message": message}
	return patch("banking.connectors.admin_request.requests.request", return_value=response)


@contextmanager
def create_successful_request(order_type: str, start_date: date, end_date: date):
	doc = frappe.new_doc("EBICS Request")
	doc.order_type = order_type
	doc.status = "Successful"
	doc.parameters = json.dumps({"start_date": start_date.isoformat(), "end_date": end_date.isoformat()})
	doc.save()

	yield doc

	doc.delete()
