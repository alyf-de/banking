# Copyright (c) 2026, ALYF GmbH and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from banking.ebics.utils import import_ebics_json


class TestEBICSUtils(FrappeTestCase):
	@patch("banking.ebics.utils.get_bank_account", return_value="Test Bank Account")
	@patch("banking.ebics.utils.process_camt_document")
	@patch("fintech.sepa.CAMTDocument")
	def test_import_batch_without_download_does_not_split(
		self, camt_document_class, process_camt_document, _get_bank_account
	):
		camt_document = camt_document_class.return_value
		camt_document.iban = "DE89370400440532013000"
		user = SimpleNamespace(
			bank="Test Bank",
			company="Test Company",
			start_date=None,
			split_batch_transactions=True,
			download_batch_transactions=False,
		)

		import_ebics_json(user, {"camt053.xml": b"<Document />"})

		process_camt_document.assert_called_once_with(
			camt_document,
			"Test Bank Account",
			"Test Company",
			None,
			False,
		)
