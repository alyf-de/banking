# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from banking.testing_utils import make_bank_transaction


class TestEnforcePositiveValues(FrappeTestCase):
	def test_deposit_values_are_normalized(self):
		doc = make_bank_transaction(
			company=None,
			run_before_validate=True,
			deposit=-2.0,
			withdrawal=0.0,
			included_fee=-1.0,
			excluded_fee=-1.0,
		)

		self.assertEqual(doc.deposit, 1.0)
		self.assertEqual(doc.withdrawal, 0.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)
		self.assertEqual(doc.unallocated_amount, 1.0)

	def test_withdrawal_values_are_normalized(self):
		doc = make_bank_transaction(
			company=None,
			run_before_validate=True,
			deposit=0.0,
			withdrawal=-1.0,
			included_fee=-1.0,
			excluded_fee=-1.0,
		)

		self.assertEqual(doc.deposit, 0.0)
		self.assertEqual(doc.withdrawal, 2.0)
		self.assertEqual(doc.included_fee, 2.0)
		self.assertEqual(doc.excluded_fee, 0.0)
		self.assertEqual(doc.unallocated_amount, 2.0)

	def test_negative_withdrawal_with_positive_excluded_fee(self):
		doc = make_bank_transaction(
			company=None,
			run_before_validate=True,
			deposit=0.0,
			withdrawal=-10.0,
			included_fee=0.0,
			excluded_fee=1.0,
		)

		self.assertEqual(doc.deposit, 0.0)
		self.assertEqual(doc.withdrawal, 11.0)
		self.assertEqual(doc.included_fee, 1.0)
		self.assertEqual(doc.excluded_fee, 0.0)
		self.assertEqual(doc.unallocated_amount, 11.0)

	def test_negative_deposit_with_positive_excluded_fee(self):
		doc = make_bank_transaction(
			company=None,
			run_before_validate=True,
			deposit=-10.0,
			withdrawal=0.0,
			included_fee=0.0,
			excluded_fee=1.0,
		)

		self.assertEqual(doc.deposit, 9.0)
		self.assertEqual(doc.withdrawal, 0.0)
		self.assertEqual(doc.included_fee, 1.0)
		self.assertEqual(doc.excluded_fee, 0.0)
		self.assertEqual(doc.unallocated_amount, 9.0)

	def test_none_values_are_left_untouched(self):
		doc = make_bank_transaction(
			company=None,
			run_before_validate=True,
			deposit=None,
			withdrawal=None,
			included_fee=None,
			excluded_fee=None,
		)

		self.assertIsNone(doc.deposit)
		self.assertIsNone(doc.withdrawal)
		self.assertIsNone(doc.included_fee)
		self.assertIsNone(doc.excluded_fee)
		self.assertEqual(doc.unallocated_amount, 0.0)
