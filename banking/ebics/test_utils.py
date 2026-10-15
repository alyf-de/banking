# Copyright (c) 2026, ALYF GmbH and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from banking.ebics.utils import (
	UnresolvedBatchTransactionError,
	create_bank_transaction,
	get_bank_account,
	import_ebics_json,
	process_camt_document,
)
from banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.test_bank_reconciliation_tool_beta import (
	create_bank,
)
from banking.testing_utils import create_currency_account, get_bank_parent_account

EXTRA_TEST_RECORD_DEPENDENCIES = ["Company"]


class TestEBICSUtils(UnitTestCase):
	class EmptyBatchTransaction:
		batch = True
		status = None

		def __len__(self):
			return 0

	@patch("banking.ebics.utils.get_bank_account", return_value="Test Bank Account")
	@patch("banking.ebics.utils.process_camt_document")
	def test_import_batch_without_download_does_not_skip(self, process_camt_document, _get_bank_account):
		# fintech.sepa cannot be imported until fintech.register() has been called.
		camt_document_class = MagicMock()
		camt_document = camt_document_class.return_value
		camt_document.iban = "DE89370400440532013000"
		user = SimpleNamespace(
			bank="Test Bank",
			start_date=None,
			split_batch_transactions=True,
			download_batch_transactions=False,
		)

		with patch.dict("sys.modules", {"fintech.sepa": MagicMock(CAMTDocument=camt_document_class)}):
			import_ebics_json(user, {"camt053.xml": b"<Document />"})

		process_camt_document.assert_called_once_with(
			camt_document,
			"Test Bank Account",
			earliest_date=None,
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
			split_batch_transactions=True,
			skip_unresolved_batch_transactions=False,
		)

		create_sepa_bank_transaction.assert_called_once_with(
			"Test Bank Account",
			transaction,
			transaction_id="batch-id",
			start_date=None,
		)

	@patch("frappe.db.exists", return_value=False)
	@patch("banking.ebics.utils.get_transaction_id", return_value="batch-id")
	def test_process_unresolved_batch_with_download_is_skipped(self, _get_transaction_id, _exists):
		with self.assertRaises(UnresolvedBatchTransactionError):
			process_camt_document(
				[self.EmptyBatchTransaction()],
				"Test Bank Account",
				split_batch_transactions=True,
				skip_unresolved_batch_transactions=True,
			)

	@patch("frappe.db.exists", return_value=True)
	@patch("banking.ebics.utils.create_sepa_bank_transaction")
	@patch("banking.ebics.utils.get_transaction_id", return_value="batch-id")
	def test_process_unresolved_batch_already_imported(
		self, _get_transaction_id, create_sepa_bank_transaction, _exists
	):
		# E.g. an intraday sync already split the batch and camt.054 is not delivered again.
		transaction = self.EmptyBatchTransaction()

		process_camt_document(
			[transaction],
			"Test Bank Account",
			split_batch_transactions=True,
			skip_unresolved_batch_transactions=True,
		)

		create_sepa_bank_transaction.assert_not_called()


class TestEBICSMultipleCompanies(IntegrationTestCase):
	def test_one_bank_imports_for_several_companies(self):
		"""One EBICS User (one bank) finds Bank Accounts of any company by IBAN."""
		create_bank("_Test Same Branch Bank", swift_number="BELADEBE")

		for company, currency, iban in (
			("_Test Company", "INR", "DE02100500000054540402"),
			("_Test Company 1", "USD", "DE65100500000001234567"),
		):
			account = create_currency_account(
				currency, get_bank_parent_account(company), f"_Test_EBICS_{currency}", company
			)
			frappe.new_doc(
				"Bank Account",
				account_name=f"_Test_EBICS_{currency}",
				bank="_Test Same Branch Bank",
				iban=iban,
				is_company_account=1,
				company=company,
				account=account.name,
			).insert()

			bank_account = get_bank_account(iban, "_Test Same Branch Bank")
			create_bank_transaction(
				bank_account,
				transaction_id=f"_Test_EBICS_{iban}",
				date=frappe.utils.today(),
				deposit=100,
				currency=currency,
			)

			self.assertEqual(
				frappe.db.get_value("Bank Transaction", {"bank_account": bank_account}, "company"), company
			)
