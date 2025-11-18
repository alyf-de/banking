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


class TestBankingSettings(FrappeTestCase):
	def test_successful_request_exists(self):
		with create_successful_request("C53", date(2025, 1, 1), date(2025, 1, 1)) as request:
			self.assertTrue(successful_request_exists(None, request.order_type, date(2025, 1, 1)))
			self.assertFalse(successful_request_exists(None, request.order_type, date(2025, 1, 2)))


@contextmanager
def create_successful_request(order_type: str, start_date: date, end_date: date):
	doc = frappe.new_doc("EBICS Request")
	doc.order_type = order_type
	doc.status = "Successful"
	doc.parameters = json.dumps({"start_date": start_date.isoformat(), "end_date": end_date.isoformat()})
	doc.save()

	yield doc

	doc.delete()
