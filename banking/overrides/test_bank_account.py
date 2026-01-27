# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError
from banking.utils import create_bank_account, create_currency_account


class TestBankReconciliationRule(FrappeTestCase):
	def test_validate_account_currencies(self):
		parent_account = frappe.db.get_value("Account", {"is_group": 1})
		account_1 = create_currency_account("EUR", parent_account)
		account_2 = create_currency_account("USD", parent_account)

		with self.assertRaises(CurrencyMismatchError):
			create_bank_account(account_1.name, bank_fee_account=account_2.name)

		account_1.delete(ignore_permissions=True, delete_permanently=True)
		account_2.delete(ignore_permissions=True, delete_permanently=True)
