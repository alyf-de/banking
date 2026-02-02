# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError
from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	NoFiltersError,
)
from banking.utils import TEST_COMPANY, create_bank_account, create_currency_account


class TestBankReconciliationRule(FrappeTestCase):
	def test_validate_account_currencies(self):
		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account("USD", parent_account)

		ba = create_bank_account(account_1.name)

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
