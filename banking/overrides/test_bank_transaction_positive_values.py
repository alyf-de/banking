# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from banking.overrides.bank_transaction import enforce_positive_values


class TestEnforcePositiveValues(FrappeTestCase):
	def test_deposit_values_are_normalized(self):
		doc = frappe.new_doc("Bank Transaction")

		doc.deposit = -2.0
		doc.withdrawal = 0.0
		doc.included_fee = -1.0
		doc.excluded_fee = -1.0

		enforce_positive_values(doc)

		self.assertEqual(doc.deposit, 1.0)
		self.assertEqual(doc.withdrawal, 0.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)

	def test_withdrawal_values_are_normalized(self):
		doc = frappe.new_doc("Bank Transaction")

		doc.deposit = 0.0
		doc.withdrawal = -1.0
		doc.included_fee = -1.0
		doc.excluded_fee = -1.0

		enforce_positive_values(doc)

		self.assertEqual(doc.deposit, 0.0)
		self.assertEqual(doc.withdrawal, 2.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)

	def test_none_values_are_left_untouched(self):
		doc = frappe.new_doc("Bank Transaction")

		doc.deposit = None
		doc.withdrawal = None
		doc.included_fee = None
		doc.excluded_fee = None

		enforce_positive_values(doc)

		self.assertIsNone(doc.deposit)
		self.assertIsNone(doc.withdrawal)
		self.assertIsNone(doc.included_fee)
		self.assertIsNone(doc.excluded_fee)
