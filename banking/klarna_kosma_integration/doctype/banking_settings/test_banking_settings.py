# Copyright (c) 2022, ALYF GmbH and Contributors
# See license.txt

import json
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from banking.klarna_kosma_integration.doctype.banking_settings.banking_settings import (
	successful_request_exists,
)
from banking.testing_utils import (
	create_bank_account,
	create_currency_account,
	get_bank_parent_account,
	set_automatic_bank_fee_entries,
)


class TestBankingSettings(IntegrationTestCase):
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


@contextmanager
def create_successful_request(order_type: str, start_date: date, end_date: date):
	doc = frappe.new_doc("EBICS Request")
	doc.order_type = order_type
	doc.status = "Successful"
	doc.parameters = json.dumps({"start_date": start_date.isoformat(), "end_date": end_date.isoformat()})
	doc.save()

	yield doc

	doc.delete()
