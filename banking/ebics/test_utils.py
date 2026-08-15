# Copyright (c) 2026, ALYF GmbH and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

from fintech import sepa
from frappe.tests.utils import FrappeTestCase

from banking.ebics.utils import UnresolvedBatchTransactionError, import_ebics_json, process_camt_document


class TestEBICSUtils(FrappeTestCase):
	class EmptyBatchTransaction:
		batch = True
		status = None

		def __len__(self):
			return 0

	@patch("banking.ebics.utils.get_bank_account", return_value="Test Bank Account")
	@patch("banking.ebics.utils.process_camt_document")
	@patch.object(sepa, "CAMTDocument")
	def test_import_batch_without_download_does_not_skip(
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
			split_batch_transactions=True,
			skip_unresolved_batch_transactions=False,
		)

	@patch("banking.ebics.utils.create_sepa_bank_transaction")
	@patch("banking.ebics.utils.get_transaction_id", return_value="batch-id")
	def test_process_unresolved_batch_without_download_as_single_transaction(
		self, _get_transaction_id, create_sepa_bank_transaction
	):
		transaction = self.EmptyBatchTransaction()

		process_camt_document(
			[transaction],
			"Test Bank Account",
			"Test Company",
			split_batch_transactions=True,
			skip_unresolved_batch_transactions=False,
		)

		create_sepa_bank_transaction.assert_called_once_with(
			"Test Bank Account",
			"Test Company",
			transaction,
			transaction_id="batch-id",
			start_date=None,
		)

	@patch("banking.ebics.utils.get_transaction_id", return_value="batch-id")
	def test_process_unresolved_batch_with_download_is_skipped(self, _get_transaction_id):
		with self.assertRaises(UnresolvedBatchTransactionError):
			process_camt_document(
				[self.EmptyBatchTransaction()],
				"Test Bank Account",
				"Test Company",
				split_batch_transactions=True,
				skip_unresolved_batch_transactions=True,
			)
