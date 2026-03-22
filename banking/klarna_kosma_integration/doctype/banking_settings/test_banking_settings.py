# Copyright (c) 2022, ALYF GmbH and Contributors
# See license.txt

import json
from contextlib import contextmanager
from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.klarna_kosma_integration.doctype.banking_settings.banking_settings import (
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

	def test_cannot_enable_automatic_fee_entries_without_fee_accounts_for_all_company_bank_accounts(
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


@contextmanager
def create_successful_request(order_type: str, start_date: date, end_date: date):
	doc = frappe.new_doc("EBICS Request")
	doc.order_type = order_type
	doc.status = "Successful"
	doc.parameters = json.dumps({"start_date": start_date.isoformat(), "end_date": end_date.isoformat()})
	doc.save()

	yield doc

	doc.delete()
