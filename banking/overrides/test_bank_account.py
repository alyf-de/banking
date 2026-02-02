# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.exceptions import CurrencyMismatchError
from banking.utils import TEST_COMPANY, create_bank_account, create_currency_account


class TestBankReconciliationRule(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		# these should be cleaned up by the DB rollback of FrappeTestCase
		parent_account = frappe.db.get_value("Account", {"is_group": 1, "company": TEST_COMPANY})
		cls.account_1 = create_currency_account("EUR", parent_account)
		cls.account_2 = create_currency_account("USD", parent_account)

	def test_validate_account_currencies(self):
		with self.assertRaises(CurrencyMismatchError):
			create_bank_account(self.account_1.name, bank_fee_account=self.account_2.name)
