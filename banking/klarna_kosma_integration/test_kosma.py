import json
import frappe

from frappe.client import get_count
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, get_datetime, nowdate

from banking.connectors.kosma_transaction import KosmaTransaction
from banking.demo_responses.test_responses import (
	accounts_response_1,
	bank_data_response,
	consent_response,
	flow_response,
	session_response,
	transactions_consent_response
)
from banking.klarna_kosma_integration.doctype.klarna_kosma_settings.klarna_kosma_settings import add_bank_accounts
from banking.klarna_kosma_integration.kosma import Kosma
from banking.klarna_kosma_integration.utils import (
	add_bank,
	create_bank_transactions,
	create_session_doc,
	get_account_name,
)

from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account


class TestKosma(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		doc = frappe.get_single("Klarna Kosma Settings")
		doc.enabled = True
		doc.client_id = "AB104056"
		doc.env = "Playground"
		doc.api_token = "xabsttcpQr5"
		doc.save()

		default_bank_account = frappe.db.get_value("Company", "Bolt Trades", "default_bank_account")
		if default_bank_account is None:
			frappe.db.set_value(
				"Company",
				"Bolt Trades",
				"default_bank_account",
				get_default_bank_cash_account("Bolt Trades", "Cash").get("account")
			)

		return super().setUpClass()

	@classmethod
	def tearDownClass(cls):
		doc = frappe.get_single("Klarna Kosma Settings")
		doc.enabled = False
		doc.save()

	def tearDown(self):
		# Required as session id is static in test response
		# but also has to be a unique primary key
		frappe.db.delete("Klarna Kosma Session")

	def test_kosma_obj(self):
		"""Test if Kosma objects are initialised correctly"""
		flow_obj = Kosma().get_flow(
			from_date=add_days(nowdate(), -60)
		)
		self.assertEqual(flow_obj.api_token, "xabsttcpQr5")
		self.assertEqual(
			flow_obj.base_url,
			"https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/"
		)

		consent_obj = Kosma().get_consent()
		self.assertEqual(consent_obj.api_token, "xabsttcpQr5")
		self.assertEqual(
			consent_obj.base_consent_url,
			"https://api.openbanking.playground.klarna.com/xs2a/v1/consents/"
		)

		headers = consent_obj.get_headers()
		self.assertEqual(
			headers.get("Authorization"), "Token xabsttcpQr5"
		)

	def test_kosma_session(self):
		"""Test creation of Kosma session and updation via flow"""
		create_session_doc(session_response)

		# Test if session was created within the app
		self.assertTrue(
			frappe.db.exists("Klarna Kosma Session", session_response.session_id_short)
		)
		session_doc = frappe.get_doc("Klarna Kosma Session", session_response.session_id_short)
		self.assertEqual(session_doc.status, "Running")
		self.assertEqual(session_doc.get_password("session_id"), "xyz123")
		self.assertTrue(json.loads(session_doc.consent_scope))

		Kosma().update_session_with_flow(session_response, flow_response)

		# Test if flow is updated in session doc
		session_doc.reload()
		self.assertEqual(session_doc.get_password("flow_id"), "e9fon1j1f03pq329svvrjqid1h2ikutf")
		self.assertEqual(session_doc.flow_state, "CONSUMER_INPUT_NEEDED")

	def test_bank_and_accounts_creation(self):
		"""Test if bank and accounts response is parsed and mapped correctly"""
		create_session_doc(session_response)
		Kosma().update_session_with_flow(session_response, flow_response)

		bank_name = add_bank(bank_data_response)
		bank_doc = frappe.get_doc("Bank", bank_name)

		self.assertEqual(bank_doc.name, "Testbank")

		add_bank_accounts(
			accounts=accounts_response_1.result,
			company="Bolt Trades",
			bank_name="Testbank"
		)

		bank_doc.reload()
		test_account_dict = accounts_response_1.result["accounts"][0]
		account_name = get_account_name(test_account_dict)

		self.assertEqual(bank_doc.swift_number, "TESTDE10XXX")

		self.assertEqual(get_count("Bank Account"), 5)
		self.assertEqual(account_name, "My checking account (Max Mustermann)")
		self.assertTrue(frappe.db.exists("Bank Account", f"{account_name} - {bank_name}"))

		account_doc = frappe.get_doc("Bank Account", f"{account_name} - {bank_name}")
		self.assertEqual(account_doc.bank, bank_name)
		self.assertEqual(account_doc.account, get_default_bank_cash_account("Bolt Trades", "Cash").get("account"))
		self.assertEqual(account_doc.iban, test_account_dict.get("iban"))
		self.assertEqual(account_doc.bank_account_no, test_account_dict.get("account_number"))
		self.assertEqual(account_doc.kosma_account_id, test_account_dict.get("id"))
		self.assertFalse(account_doc.last_integration_date)

	def test_transactions_creation(self):
		"""Test if transactions response is parsed and mapped correctly"""
		# Create Bank and accounts before inserting transaction
		# closest to real flow
		create_session_doc(session_response)
		Kosma().update_session_with_flow(session_response, flow_response)
		bank_name = add_bank(bank_data_response)
		add_bank_accounts(
			accounts=accounts_response_1.result,
			company="Bolt Trades",
			bank_name="Testbank"
		)

		# Process trasaction response
		transaction = KosmaTransaction(transactions_consent_response)
		self.assertFalse(transaction.is_next_page())

		create_bank_transactions(
			account=f"My checking account (Max Mustermann) - {bank_name}",
			transactions=transaction.transaction_list
		)

		test_transn_dict = transaction.transaction_list[0]
		test_transn_doc = frappe.get_doc(
			"Bank Transaction",
			{"transaction_id": test_transn_dict.get("transaction_id")}
		)

		self.assertEqual(get_count("Bank Transaction"), 17)
		self.assertEqual(test_transn_doc.withdrawal, 3242.29)
		self.assertEqual(test_transn_doc.deposit, 0.0)
		self.assertEqual(test_transn_doc.status, "Settled")
		self.assertEqual(test_transn_doc.date, getdate("2022-12-03"))
		self.assertEqual(test_transn_doc.kosma_party_name, "Hans Mustermann")

		last_sync_date = max(
			row.get("value_date") or row.get("date") for row in transaction.transaction_list
		)
		actual_last_sync_date = frappe.db.get_value(
			"Bank Account",
			f"My checking account (Max Mustermann) - {bank_name}",
			"last_integration_date"
		)

		# Test last sync date correctness
		self.assertEqual(getdate(last_sync_date), actual_last_sync_date)

	def test_bank_consent_set_get(self):
		from banking.klarna_kosma_integration.utils import get_consent_data, get_consent_start_date
		from erpnext.accounts.utils import get_fiscal_year

		create_session_doc(session_response)
		kosma = Kosma()
		kosma.update_session_with_flow(session_response, flow_response)

		bank_name = add_bank(bank_data_response)

		consent_data = get_formatted_consent()
		kosma.set_consent(
			consent=consent_data,
			bank_name=bank_name,
			session_id_short=session_response.session_id_short,
			company="Bolt Trades"
		)

		consent_id, consent_token = get_consent_data(bank_name, "Bolt Trades")
		self.assertEqual(consent_id, consent_response.get("consent_id"))
		self.assertEqual(consent_token, consent_response.get("consent_token"))

		start_date = get_consent_start_date(session_response.session_id_short)
		current_fiscal_year = get_fiscal_year(nowdate(), as_dict=True)

		# check if consent start date is start of fiscal year
		self.assertEqual(getdate(start_date), current_fiscal_year.year_start_date)


def get_formatted_consent():
	return {
		"consent_id": consent_response.get("consent_id"),
		"consent_token": consent_response.get("consent_token"),
		"consent_expiry": add_days(get_datetime(), 90),
	}