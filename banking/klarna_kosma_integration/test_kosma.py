import frappe
from frappe.tests.utils import FrappeTestCase
from banking.klarna_kosma_integration.admin import Admin
from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)


class TestKosma(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		doc = frappe.get_single("Banking Settings")
		doc.enabled = True
		doc.api_token = "xabsttcpQr5"
		doc.customer_id = "ADCB8A"
		doc.admin_endpoint = "http://banking-admin:8000"
		doc.save()

		default_bank_account = frappe.db.get_value(
			"Company", "Bolt Trades", "default_bank_account"
		)
		if default_bank_account is None:
			frappe.db.set_value(
				"Company",
				"Bolt Trades",
				"default_bank_account",
				get_default_bank_cash_account("Bolt Trades", "Cash").get("account"),
			)

		return super().setUpClass()

	@classmethod
	def tearDownClass(cls):
		doc = frappe.get_single("Banking Settings")
		doc.enabled = False
		doc.save()

	def test_admin_obj(self):
		"""Test if Admin objects are initialised correctly"""
		admin = Admin()
		self.assertEqual(admin.api_token, "xabsttcpQr5")
		self.assertEqual(admin.customer_id, "ADCB8A")
<<<<<<< HEAD

	def test_kosma_session(self):
		"""Test creation of Kosma session and updation via flow"""
		session_data = session_response.session_data
		create_session_doc(session_data, session_response.flow_data)

		# Test if session was created within the app
		self.assertTrue(
			frappe.db.exists("Klarna Kosma Session", session_data.get("session_id_short"))
		)
		session_doc = frappe.get_doc(
			"Klarna Kosma Session", session_data.get("session_id_short")
		)
		self.assertEqual(session_doc.status, "Running")
		self.assertEqual(session_doc.get_password("session_id"), "xyz123")
		self.assertTrue(json.loads(session_doc.consent_scope))

		# Test if flow is updated in session doc
		self.assertEqual(
			session_doc.get_password("flow_id"), "e9fon1j1f03pq329svvrjqid1h2ikutf"
		)
		self.assertEqual(session_doc.flow_state, "CONSUMER_INPUT_NEEDED")

	def test_bank_and_accounts_creation(self):
		"""Test if bank and accounts response is parsed and mapped correctly"""
		create_session_doc(session_response.session_data, session_response.flow_data)

		bank_name = add_bank(bank_data_response)
		bank_doc = frappe.get_doc("Bank", bank_name)

		self.assertEqual(bank_doc.name, "Testbank")

		acc = create_account_for_bank_account("Personal Account")
		test_account_dict = accounts_response_1.result["accounts"][0]
		add_bank_account(
			account_data=test_account_dict,
			gl_account=acc,
			company="Bolt Trades",
			bank_name="Testbank",
		)

		bank_doc.reload()
		account_name = get_account_name(test_account_dict)

		self.assertEqual(bank_doc.swift_number, "TESTDE10XXX")

		self.assertEqual(account_name, "My checking account (Max Mustermann)")
		self.assertTrue(frappe.db.exists("Bank Account", f"{account_name} - {bank_name}"))

		account_doc = frappe.get_doc("Bank Account", f"{account_name} - {bank_name}")
		self.assertEqual(account_doc.bank, bank_name)
		self.assertEqual(
			account_doc.account,
			acc,
		)
		self.assertEqual(account_doc.iban, test_account_dict.get("iban"))
		self.assertEqual(account_doc.bank_account_no, test_account_dict.get("account_number"))
		self.assertEqual(account_doc.kosma_account_id, test_account_dict.get("id"))
		self.assertFalse(account_doc.last_integration_date)

	def test_bank_and_accounts_creation_without_alias(self):
		"""Test if bank account is created without an alias in the response."""
		create_session_doc(session_response.session_data, session_response.flow_data)

		bank_name = add_bank(bank_data_response)
		bank_doc = frappe.get_doc("Bank", bank_name)

		self.assertEqual(bank_doc.name, "Testbank")

		acc = create_account_for_bank_account("Max Mustermann")
		test_account_dict = accounts_response_2.result["accounts"][0]
		add_bank_account(
			account_data=test_account_dict,
			gl_account=acc,
			company="Bolt Trades",
			bank_name="Testbank",
		)

		bank_doc.reload()
		account_name = get_account_name(test_account_dict)

		self.assertEqual(account_name, "DE06000000000023456789")
		self.assertTrue(frappe.db.exists("Bank Account", f"{account_name} - {bank_name}"))

	def test_transactions_creation(self):
		"""Test if transactions response is parsed and mapped correctly"""
		# Create Bank and accounts before inserting transaction
		# closest to real flow
		create_session_doc(session_response.session_data, session_response.flow_data)

		bank_name = add_bank(bank_data_response)
		acc = create_account_for_bank_account("Business Account")
		test_account_dict = accounts_response_1.result["accounts"][1]
		add_bank_account(
			account_data=test_account_dict,
			gl_account=acc,
			company="Bolt Trades",
			bank_name="Testbank",
		)

		# Process trasaction response
		transaction = AdminTransaction(transactions_consent_response)
		self.assertFalse(transaction.is_next_page())

		create_bank_transactions(
			account=f"My checking account (Max Mustermann) - {bank_name}",
			transactions=transaction.transaction_list,
		)

		test_transn_dict = transaction.transaction_list[0]
		test_transn_doc = frappe.get_doc(
			"Bank Transaction", {"transaction_id": test_transn_dict.get("transaction_id")}
		)

		self.assertEqual(get_count("Bank Transaction"), 17)
		self.assertEqual(test_transn_doc.withdrawal, 3242.29)
		self.assertEqual(test_transn_doc.deposit, 0.0)
		self.assertEqual(test_transn_doc.status, "Unreconciled")
		self.assertEqual(test_transn_doc.date, getdate("2022-12-03"))
		self.assertEqual(test_transn_doc.bank_party_name, "Hans Mustermann")
		self.assertEqual(test_transn_doc.bank_party_iban, "DE18000000006636981175")
		self.assertEqual(test_transn_doc.bank_party_account_number, "000000006636981175")

		last_sync_date = max(
			row.get("value_date") or row.get("date") for row in transaction.transaction_list
		)
		actual_last_sync_date = frappe.db.get_value(
			"Bank Account",
			f"My checking account (Max Mustermann) - {bank_name}",
			"last_integration_date",
		)

		# Test last sync date correctness
		self.assertEqual(getdate(last_sync_date), actual_last_sync_date)

	def test_bank_consent_set_get(self):
		from banking.klarna_kosma_integration.utils import (
			get_consent_data,
		)

		session_data = session_response.session_data
		create_session_doc(session_data, session_response.flow_data)
		bank_name = add_bank(bank_data_response)

		consent_data = get_formatted_consent()
		Admin().set_consent(
			consent=consent_data,
			bank_name=bank_name,
			session_id_short=session_data.get("session_id_short"),
			company="Bolt Trades",
		)

		consent_id, consent_token = get_consent_data(bank_name, "Bolt Trades")
		self.assertEqual(consent_id, consent_response.get("consent_id"))
		self.assertEqual(consent_token, consent_response.get("consent_token"))


def get_formatted_consent():
	return {
		"consent_id": consent_response.get("consent_id"),
		"consent_token": consent_response.get("consent_token"),
		"consent_expiry": add_days(get_datetime(), 90),
	}


def create_account_for_bank_account(account_name: str):
	gl_account = frappe.get_doc(
		{
			"doctype": "Account",
			"company": "Bolt Trades",
			"parent_account": "Current Assets - BT",
			"account_type": "Bank",
			"is_group": 0,
			"account_name": account_name,
		}
	).insert()
	return gl_account.name
=======
>>>>>>> cd12768 (feat!: remove kosma (#168))
