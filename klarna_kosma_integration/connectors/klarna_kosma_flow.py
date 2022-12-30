# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict

import frappe
import requests

from frappe import _

from klarna_kosma_integration.connectors.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from klarna_kosma_integration.klarna_kosma_integration.utils import (
	add_bank,
	get_session_flow_ids,
)


class KlarnaKosmaFlow(KlarnaKosmaConnector):
	def __init__(self) -> None:
		super(KlarnaKosmaFlow, self).__init__()

	def get_client_token(self, current_flow) -> Dict[str, str]:
		"""
		Returns Client Token to render XS2A App & Short Session ID to track session
		"""
		session_details = self._start_session()
		flow_data = self._start_flow(
			current_flow,
			session_id_short=session_details.get("session_id_short"),
			flows=session_details.get("flows"),
		)

		session_data = {
			"session_id_short": session_details.get("session_id_short"),
			"client_token": flow_data.get("client_token"),
		}
		return session_data

	def fetch_accounts(self, session_id_short: str):
		"""
		- Fetch Accounts using Flow API
		- Create Bank Record from Session Bank data (better UX, less user interaction)
		- Set consent token in Bank record
		"""
		try:
			session_id, flow_id = get_session_flow_ids(session_id_short)

			flow_response = requests.get(
				url=self.base_url + "{0}/flows/{1}".format(session_id, flow_id),
				headers=self._get_headers(),
			)
			flow_response.raise_for_status()
			flow_response_val = flow_response.json()

			bank_name = self._get_session_bank(session_id)
			self._update_flow_state(flow_response_val, session_id_short)
			self._set_consent_token(session_id, bank_name)

			flow_response_val["data"]["result"]["bank_name"] = bank_name

			return flow_response_val
		except Exception:
			self._handle_exception(_("Failed to get Bank Accounts."))
		finally:
			self._end_session(session_id, session_id_short)

	def _start_session(self):
		"""
		Start a Kosma Session and return session details
		"""
		dates = self._get_session_flow_date_range()
		data = {
			"psu": self.psu,
			"consent_scope": {"lifetime": 90, "accounts": dates, "transactions": dates},
		}

		try:
			session_response = requests.put(
				url=self.base_url, headers=self._get_headers(), data=json.dumps(data)
			)
			session_response.raise_for_status()
			session_response_val = session_response.json()  # TODO: check if json else None

			session_data = session_response_val.get("data")
			self._create_session_doc(session_data, session_config=data)

			return session_data
		except Exception:
			self._handle_exception(_("Failed to start Kosma Session."))

	def _create_session_doc(self, session_data: Dict, session_config: Dict) -> None:
		session_doc = frappe.get_doc(
			{
				"doctype": "Klarna Kosma Session",
				"session_id_short": session_data.get("session_id_short"),
				"session_id": session_data.get("session_id"),
				"session_config": json.dumps(session_config),
				"status": "Running",
			}
		)
		session_doc.insert()

	def _start_flow(
		self, current_flow: str, session_id_short: str, flows: Dict[str, str] = None
	):
		"""
		Start flow > Generate & return Client Token
		"""
		flow_link = flows.get(current_flow, "")
		data = (
			{} if current_flow == "accounts" else self._get_session_flow_date_range(is_flow=True)
		)

		try:
			flow_response = requests.put(
				url=flow_link, headers=self._get_headers(), data=json.dumps(data)
			)
			flow_response.raise_for_status()
			flow_response_data = flow_response.json().get("data", {})

			# Update Flow info in Session Doc
			session_doc = frappe.get_doc("Klarna Kosma Session", session_id_short)
			session_doc.update(
				{
					"flow_id": flow_response_data.get("flow_id"),
					"flow_state": flow_response_data.get("state"),
				}
			)
			session_doc.save()

			return flow_response_data
		except Exception:
			self._handle_exception(_("Failed to start Kosma Flow."))

	def _end_session(self, session_id: str = None, session_id_short: str = None):
		"""
		Close a Kosma Session
		"""
		try:
			requests.delete(
				url=self.base_url + session_id,
				headers=self._get_headers(),
			)
			frappe.db.set_value("Klarna Kosma Session", session_id_short, "status", "Closed")
			frappe.db.commit()
		except Exception:
			self._handle_exception(_("Failed to end Kosma session"))

	def _get_session_bank(self, session_id: str):
		"""
		Get Flow session's chosen Bank and create Bank record if absent.
		"""
		session_data_response = requests.get(
			url=f"{self.base_url}{session_id}", headers=self._get_headers()
		)
		session_data_response.raise_for_status()
		session_data = session_data_response.json()

		bank_data = session_data.get("data", {}).get("bank", {})
		bank_name = add_bank(bank_data)

		return bank_name


# def sync_transactions(account: str, session_id_short: str):
# 	"""
# 	[Not used but API maintained for future use]
# 	"""
# 	start_date = KosmaAccount.last_sync_date(account)

# 	kosma = KlarnaKosmaFlow()
# 	kosma.fetch_transactions(account, start_date, session_id_short)


# def fetch_transactions(self, account: str, start_date: str, session_id_short: str):
# 	"""
# 	[Not in use. Kept for future scope.]
# 	Fetch Transactions using Flow API and insert records after each page (Results could be paginated)
# 	"""
# 	# todo: CHECK IF WORKING (shows server issue currently), handle 'incomplete: true' in response
# 	next_page = True
# 	data = KosmaTransaction.payload(account, start_date, flow=True)

# 	session_id, flow_id = get_session_flow_ids(session_id_short)
# 	flow_url = f"{self.base_url}{session_id}/flows/{flow_id}"

# 	try:
# 		while next_page:
# 			transactions_resp = requests.get(
# 				url=flow_url,
# 				headers=self._get_headers(content_type="application/json;charset=utf-8"),
# 				data=json.dumps(data),
# 			)
# 			transactions_resp.raise_for_status()
# 			transactions_val = transactions_resp.json()

# 			# Process Request Response
# 			self._update_flow_state(transactions_val, session_id_short)
# 			self._set_consent_token(session_id)

# 			# prep for next call
# 			transaction = KosmaTransaction(transactions_val)
# 			next_page = transaction.is_next_page()
# 			if next_page:
# 				flow_url, data = transaction.next_page_request()

# 			if transaction.transaction_list:
# 				create_bank_transactions(account, transaction.transaction_list)

# 	except Exception:
# 		self._handle_exception(_("Failed to get Bank Transactions."))
# 	finally:
# 		self._end_session(session_id, session_id_short)
