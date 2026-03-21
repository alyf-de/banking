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

TEST_COMPANY = "Bolt Trades"


def create_currency_account(currency: str, parent_account: str, account_name: str):
	acc = frappe.new_doc("Account")
	acc.account_name = account_name
	acc.account_currency = currency
	acc.parent_account = parent_account
	acc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return acc


def create_bank_account(account: str, account_name: str):
	ba = frappe.new_doc("Bank Account")
	ba.account_name = account_name
	ba.account = account
	ba.bank = "_Test_Bank"
	ba.is_company_account = 1
	ba.insert(ignore_permissions=True, ignore_links=True)
	return ba


class TestBankingSettings(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)

		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		cls.account_without_fee = create_currency_account(
			"EUR", parent_account, "_Test_Banking_Settings_Account_No_Fee"
		)
		cls.bank_account_without_fee = create_bank_account(
			cls.account_without_fee.name, "_Test_Banking_Settings_Bank_Account_No_Fee"
		)

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)

	def tearDown(self):
		frappe.db.set_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees", 0)
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
