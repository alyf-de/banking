# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	CurrencyMismatchError,
	NoFiltersError,
)


class TestBankReconciliationRule(FrappeTestCase):
	def test_validate_account_currencies(self):
		parent_account = frappe.db.get_value("Account", {"is_group": 1})
		account_1 = create_account("EUR", parent_account)
		account_2 = create_account("USD", parent_account)

		ba = frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "_Test_B_Account",
				"account": account_1.name,
				"bank": "_Test_Bank",
				"is_company_account": 1,
			}
		).insert(ignore_permissions=True, ignore_links=True)

		brr_doc = frappe.new_doc("Bank Reconciliation Rule")
		brr_doc.bank_account = ba.name
		brr_doc.target_account = account_2.name

		with self.assertRaises(CurrencyMismatchError):
			brr_doc.validate_account_currencies()

		ba.delete(delete_permanently=True, ignore_permissions=True)
		account_1.delete(delete_permanently=True, ignore_permissions=True)
		account_2.delete(delete_permanently=True, ignore_permissions=True)

	def test_validate_filters(self):
		brr_doc = frappe.new_doc("Bank Reconciliation Rule")
		brr_doc.filters = None
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()

		brr_doc.filters = "[]"
		with self.assertRaises(NoFiltersError):
			brr_doc.validate_filters()


def create_account(currency: str, parent_account: str):
	account = frappe.new_doc("Account")
	account.update(
		{
			"account_name": f"_Test_Account_{currency}",
			"account_currency": currency,
			"parent_account": parent_account,
		}
	)
	account.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return account
