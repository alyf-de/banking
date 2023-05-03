# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
from typing import Dict, Optional

import frappe
from frappe import _

from banking.connectors.admin_request import AdminRequest
from banking.connectors.admin_transaction import AdminTransaction
from banking.klarna_kosma_integration.utils import (
	account_last_sync_date,
	add_bank,
	create_bank_transactions,
	create_session_doc,
	exchange_consent_token,
	get_consent_data,
	get_consent_start_date,
	get_current_ip,
	get_from_to_date,
	get_session_flow_ids,
)


class Admin:
	"""A class that directly communicates with the Banking Admin App."""

	def __init__(self) -> None:
		self.ip_address = get_current_ip()
		self.user_agent = frappe.get_request_header("User-Agent") if frappe.request else None

		settings = frappe.get_single("Banking Settings")
		self.api_token = settings.get_password("api_token")
		self.customer_id = settings.customer_id
		self.url = settings.admin_endpoint


	@property
	def request(self):
		return AdminRequest(
			ip_address=self.ip_address,
			user_agent=self.user_agent,
			api_token=self.api_token,
			url=self.url,
			customer_id=self.customer_id,
		)


	def get_client_token(
		self,
		current_flow: str,
		account: Optional[str] = None,
		from_date: Optional[str] = None,
		to_date: Optional[str] = None,
	) -> Dict:
			account_data = {}
			if account:
				iban, account_id = frappe.db.get_value(
					"Bank Account", account, ["iban", "kosma_account_id"]
				)
				account_data = {"iban": iban, "account_id": account_id}

			from_date, to_date = get_from_to_date(from_date, to_date)

			session_flow_response = self.request.get_client_token(
				current_flow=current_flow,
				account=account_data,
				from_date=from_date,
				to_date=to_date
			)

			session_flow_response.raise_for_status()
			session_flow_response = session_flow_response.json().get("message", {})

			session_details = session_flow_response.get("session_data", {})
			flow_details = session_flow_response.get("flow_data", {})

			create_session_doc(session_details)
			self.update_session_with_flow(
				session=session_details,
				flow_data=flow_details
			)

			return {
				"session_id_short": session_details.get("session_id_short"),
				"client_token": flow_details.get("client_token"),
			}


	def flow_accounts(self, session_id_short: str, company: str) -> Dict:
		try:
			session_id, flow_id = get_session_flow_ids(session_id_short)

			accounts_response = self.request.flow_accounts(  # Fetch Accounts
				session_id, flow_id
			)
			accounts_response.raise_for_status()

			accounts_response = accounts_response.json().get("message", {})
			accounts_result = accounts_response.get("result", {})

			bank_data = accounts_result.get("bank_data")
			bank_name = self.get_session_bank(bank_data)

			# Get and store Bank Consent in Bank record
			consent = accounts_result.get("consent_data")
			self.set_consent(consent, bank_name, session_id_short, company)

			return {
				"accounts": accounts_result.get("accounts", []),
				"bank_data": bank_data
			}
		except Exception as exc:
			self.handle_exception(exc, _("Failed to get Bank Accounts."))
		finally:
			frappe.db.set_value(
				"Klarna Kosma Session",
				session_id_short,
				{
					"flow_state": accounts_response.get("state", "EXCEPTION"),
					"status": accounts_response.get("session_state") or "Running"
				}
			)


	def flow_transactions(self, account: str, session_id_short: str):
		next_page, url, offset = True, None, None
		try:
			session_id, flow_id = get_session_flow_ids(session_id_short)
			while next_page:
				response = self.request.flow_transactions(
					session_id, flow_id, url, offset
				)
				response.raise_for_status()

				transactions_value = response.json().get("message", {})

				# Process Request Response
				transaction = AdminTransaction(transactions_value)
				next_page = transaction.is_next_page()
				if next_page:
					url, offset = transaction.next_page_request()

				if transaction.transaction_list:
					create_bank_transactions(account, transaction.transaction_list, via_flow_api=True)
		except Exception as exc:
			self.handle_exception(exc, _("Failed to get Kosma Transactions."))
		finally:
			frappe.db.set_value(
				"Klarna Kosma Session",
				session_id_short,
				{
					"flow_state": transactions_value.get("state", "EXCEPTION"),
					"status": transactions_value.get("session_state", "Running")
				}
			)


	def consent_accounts(self, bank: str, company: str):
		try:
			consent_id, consent_token = get_consent_data(bank, company)

			accounts_response = self.request.consent_accounts(consent_id, consent_token)
			accounts_response_value = accounts_response.json().get("message", {})

			exchange_consent_token(accounts_response_value, bank, company)
			accounts_response.raise_for_status()

			accounts = accounts_response_value.get("result", {}).get("accounts")
			return accounts
		except Exception as exc:
			self.handle_exception(exc, _("Failed to get Bank Accounts."))


	def consent_transactions(self, account: str, start_date: str):
		account_id, bank, company = frappe.db.get_value(
			"Bank Account", account, ["kosma_account_id", "bank", "company"]
		)
		consent_id, consent_token = get_consent_data(bank, company)

		next_page, url, offset = True, None, None
		try:
			while next_page:
				response = self.request.consent_transactions(
					account_id, start_date, consent_id, consent_token, url, offset
				)
				transactions_value = response.json().get("message", {})

				new_consent_token = exchange_consent_token(transactions_value, bank, company)
				response.raise_for_status()

				# Process Request Response
				transaction = AdminTransaction(transactions_value)
				next_page = transaction.is_next_page()
				if next_page:
					url, offset = transaction.next_page_request()
					consent_token = new_consent_token

				if transaction.transaction_list:
					create_bank_transactions(account, transaction.transaction_list)
		except Exception as exc:
			self.handle_exception(exc, _("Failed to get Kosma Transactions."))


	def end_session(
		self, session_id: str, session_id_short: str
	) -> None:
		self.request.end_session(session_id)
		frappe.db.set_value("Klarna Kosma Session", session_id_short, "status", "Closed")
		frappe.db.commit()


	def update_session_with_flow(self, session: Dict, flow_data: Dict):
		"""Update Flow info in Session Doc"""
		session_id_short = session.get("session_id_short")
		session_doc = frappe.get_doc("Klarna Kosma Session", session_id_short)
		session_doc.update(
			{
				"flow_id": flow_data.get("flow_id"),
				"flow_state": flow_data.get("state"),
			}
		)
		session_doc.save()

	def get_session_bank(self, bank_data: dict):
		"""Get Bank name from session and create Bank record if absent."""
		bank_name = add_bank(bank_data)
		return bank_name


	def set_consent(
		self, consent: Dict, bank_name: str, session_id_short: str, company: str
	) -> None:
		consent["consent_start"] = get_consent_start_date(session_id_short)
		consent["session_id"] = session_id_short

		if frappe.db.exists("Bank Consent", {"bank": bank_name, "company": company}):
			bank_consent = frappe.get_doc(
				"Bank Consent", {"bank": bank_name, "company": company}
			)
		else:
			bank_consent = frappe.get_doc(
				{
					"doctype": "Bank Consent",
					"bank": bank_name,
					"company": company,
				}
			)

		bank_consent.update(consent)
		bank_consent.save()


@frappe.whitelist()
def sync_kosma_transactions(account: str, session_id_short: Optional[str] = None):
	"""Fetch and insert paginated Kosma transactions"""
	if session_id_short:
		Admin().flow_transactions(account, session_id_short)
	else:
		start_date = account_last_sync_date(account)
		Admin().consent_transactions(account, start_date)
