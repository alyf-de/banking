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
	"""A class that communicate with Banking Admin."""

	def __init__(self) -> None:
		self.ip_address = get_current_ip()

		settings = frappe.get_single("Banking Settings")
		self.api_token = settings.get_password("api_token")
		self.customer_id = settings.customer_id
		self.url = settings.admin_endpoint

	@property
	def request(self):
		return AdminRequest(
			ip_address=self.ip_address,
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

			return session_flow_response
			# TODO: error handling

			# session_name = create_session_doc(session_details)
			# self.update_session_with_flow(session=session, flow_data=flow_data)

			# return {
			# 	"session_id_short": session_details.get("session_id_short"),
			# 	"client_token": flow_data.get("client_token"),
			# }

# 	def flow_accounts(self, session_id_short: str, company: str) -> Dict:
# 		try:
# 			flow = self.get_flow()
# 			session_id, flow_id = get_session_flow_ids(session_id_short)

# 			accounts_data = flow.accounts(session_id, flow_id)  # Fetch Accounts
# 			flow.raise_for_status(accounts_data)

# 			bank_name = self.get_session_bank(flow, session_id)
# 			accounts_data["result"]["bank_name"] = bank_name

# 			# Get and store Bank Consent in Bank record
# 			consent = flow.get_consent(session_id)
# 			self.set_consent(consent, bank_name, session_id_short, company)

# 			return accounts_data
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to get Bank Accounts."))
# 		finally:
# 			flow_state = accounts_data.get("state", "EXCEPTION")
# 			frappe.db.set_value(
# 				"Klarna Kosma Session", session_id_short, "flow_state", flow_state
# 			)

# 			self.end_session(flow, session_id, session_id_short)

# 	def flow_transactions(self, account: str, session_id_short: str):
# 		next_page, url, offset = True, None, None

# 		try:
# 			flow = self.get_flow()
# 			session_id, flow_id = get_session_flow_ids(session_id_short)

# 			while next_page:
# 				transactions = flow.transactions(session_id, flow_id, url, offset)
# 				flow.raise_for_status(transactions)

# 				# Process Request Response
# 				transaction = AdminTransaction(transactions)
# 				next_page = transaction.is_next_page()
# 				if next_page:
# 					url, offset = transaction.next_page_request()

# 				if transaction.transaction_list:
# 					create_bank_transactions(account, transaction.transaction_list, via_flow_api=True)
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to get Kosma Transactions."))
# 		finally:
# 			flow_state = transactions.get("state", "EXCEPTION")
# 			frappe.db.set_value(
# 				"Klarna Kosma Session", session_id_short, "flow_state", flow_state
# 			)

# 			self.end_session(flow, session_id, session_id_short)

# 	def consent_accounts(self, bank: str, company: str):
# 		try:
# 			consent_id, consent_token = get_consent_data(bank, company)
# 			consent = self.get_consent()
# 			accounts = consent.accounts(consent_id, consent_token)

# 			exchange_consent_token(accounts, bank, company)
# 			consent.raise_for_status(accounts)

# 			accounts = accounts.get("result", {}).get("accounts")
# 			return accounts
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to get Bank Accounts."))

# 	def consent_transactions(self, account: str, start_date: str):
# 		account_id, bank, company = frappe.db.get_value(
# 			"Bank Account", account, ["kosma_account_id", "bank", "company"]
# 		)
# 		consent_id, consent_token = get_consent_data(bank, company)
# 		consent = self.get_consent()

# 		next_page, url, offset = True, None, None
# 		try:
# 			while next_page:
# 				transactions = consent.transactions(
# 					account_id, start_date, consent_id, consent_token, url, offset
# 				)

# 				new_consent_token = exchange_consent_token(transactions, bank, company)
# 				consent.raise_for_status(transactions)

# 				# Process Request Response
# 				transaction = AdminTransaction(transactions)
# 				next_page = transaction.is_next_page()
# 				if next_page:
# 					url, offset = transaction.next_page_request()
# 					consent_token = new_consent_token

# 				if transaction.transaction_list:
# 					create_bank_transactions(account, transaction.transaction_list)
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to get Kosma Transactions."))

# 	def start_session(
# 		self,
# 		flow_obj: "KlarnaKosmaFlow",
# 		flow_type: str,
# 		account: Optional[str] = None,
# 	) -> Dict:
# 		try:
# 			iban = frappe.db.get_value("Bank Account", account, "iban") if account else None

# 			session_details = flow_obj.start_session(flow_type, iban)
# 			flow_obj.raise_for_status(session_details)

# 			create_session_doc(session_details)
# 			return session_details
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to start Kosma Session."))

# 	def end_session(
# 		self, flow_obj: "KlarnaKosmaFlow", session_id: str, session_id_short: str
# 	) -> None:
# 		try:
# 			flow_obj.end_session(session_id)
# 			frappe.db.set_value("Klarna Kosma Session", session_id_short, "status", "Closed")
# 			frappe.db.commit()
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to end Kosma session"))

# 	def start_flow(
# 		self,
# 		flow_obj: "KlarnaKosmaFlow",
# 		current_flow: str,
# 		session: Dict,
# 		account: Optional[str] = None,
# 	) -> Dict:
# 		try:
# 			iban, account_id = None, None

# 			if account:
# 				iban, account_id = frappe.db.get_value(
# 					"Bank Account", account, ["iban", "kosma_account_id"]
# 				)

# 			flow_data = flow_obj.start(
# 				flows=session.get("flows"),
# 				flow_type=current_flow,
# 				iban=iban,
# 				account_id=account_id,
# 			)
# 			flow_obj.raise_for_status(flow_data)

# 			self.update_session_with_flow(session=session, flow_data=flow_data)
# 			return flow_data
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to start Kosma Flow."))

# 	def update_session_with_flow(self, session: Dict, flow_data: Dict):
# 		"""Update Flow info in Session Doc"""
# 		session_id_short = session.get("session_id_short")
# 		session_doc = frappe.get_doc("Klarna Kosma Session", session_id_short)
# 		session_doc.update(
# 			{
# 				"flow_id": flow_data.get("flow_id"),
# 				"flow_state": flow_data.get("state"),
# 			}
# 		)
# 		session_doc.save()

# 	def get_session_bank(self, flow_obj: "KlarnaKosmaFlow", session_id: str):
# 		"""Get Bank name from session and create Bank record if absent."""
# 		try:
# 			session = flow_obj.get_session(session_id)
# 			flow_obj.raise_for_status(session)

# 			bank_data = session.get("bank", {})
# 			bank_name = add_bank(bank_data)
# 			return bank_name
# 		except Exception as exc:
# 			self.handle_exception(exc, _("Failed to get Kosma Session"))

# 	def set_consent(
# 		self, consent: Dict, bank_name: str, session_id_short: str, company: str
# 	) -> None:
# 		consent["consent_start"] = get_consent_start_date(session_id_short)
# 		consent["session_id"] = session_id_short

# 		if frappe.db.exists("Bank Consent", {"bank": bank_name, "company": company}):
# 			bank_consent = frappe.get_doc(
# 				"Bank Consent", {"bank": bank_name, "company": company}
# 			)
# 		else:
# 			bank_consent = frappe.get_doc(
# 				{
# 					"doctype": "Bank Consent",
# 					"bank": bank_name,
# 					"company": company,
# 				}
# 			)

# 		bank_consent.update(consent)
# 		bank_consent.save()


# @frappe.whitelist()
# def sync_kosma_transactions(account: str, session_id_short: Optional[str] = None):
# 	"""Fetch and insert paginated Kosma transactions"""
# 	if session_id_short:
# 		Kosma().flow_transactions(account, session_id_short)
# 	else:
# 		start_date = account_last_sync_date(account)
# 		Kosma().consent_transactions(account, start_date)
