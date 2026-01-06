# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBankReconciliationRule(FrappeTestCase):
	def test_validate_account_currencies(self):
		account_1 = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "_Test_Account_EUR",
				"account_currency": "EUR",
				"parent_account": frappe.get_all("Account", filters={"is_group": 1}, pluck="name")[0],
			}
		).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		account_2 = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "_Test_Account_USD",
				"account_currency": "USD",
				"parent_account": frappe.get_all("Account", filters={"is_group": 1}, pluck="name")[0],
			}
		).insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)

		ba = frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": "_Test_B_Account",
				"account": account_1.name,
				"bank": "_Test_Bank",
				"is_company_account": 1,
				"bank_fee_account": account_2.name,
			}
		)

		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Company Account and Bank Fee Account must be in the same currency!",
		):
			ba.insert(ignore_permissions=True, ignore_links=True)

		frappe.db.delete("Bank Account", ba.name)
		frappe.db.delete("Account", account_1.name)
		frappe.db.delete("Account", account_2.name)
