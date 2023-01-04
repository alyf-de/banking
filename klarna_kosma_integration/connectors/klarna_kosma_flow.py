# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from multiprocessing import connection
from typing import Dict

import requests

from frappe import _
from frappe.utils import add_days, get_datetime


from klarna_kosma_integration.connectors.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)


class KlarnaKosmaFlow(KlarnaKosmaConnector):
	def __init__(self, config) -> None:
		super(KlarnaKosmaFlow, self).__init__(config)

	def start(self, flows: Dict, flow_type: str):
		"""
		Start flow > Generate & return Client Token
		"""
		flow_link = flows.get(flow_type, "")

		data = {}
		if flow_type == "accounts":
			data.update(self.get_date_range(is_flow=True))

		flow_response = requests.put(
			url=flow_link, headers=self.get_headers(), data=json.dumps(data)
		)
		flow_response_data = flow_response.json().get("data", {})

		return flow_response_data

	def accounts(self, session_id: str, flow_id: str):
		"""
		- Fetch Accounts using Flow API
		- Create Bank Record from Session Bank data (better UX, less user interaction)
		- Set consent token in Bank record
		"""
		flow_response = requests.get(
			url=f"{self.access.base_url}{session_id}/flows/{flow_id}",
			headers=self.access.get_headers(),
		)
		flow_response_val = flow_response.json().get("data", {})

		# bank_name = self._get_session_bank(session_id)
		# self._update_flow_state(flow_response_val, session_id_short)
		# self._set_consent_token(session_id, bank_name)

		# flow_response_val["data"]["result"]["bank_name"] = bank_name

		return flow_response_val
		# finally:
		# 	self._end_session(session_id, session_id_short)

	def start_session(self):
		"""
		Start a Kosma Session and return session details
		"""
		dates = self.get_date_range()
		data = {
			"psu": self.psu,
			"consent_scope": {"lifetime": 90, "accounts": dates, "transactions": dates},
		}

		session_response = requests.put(
			url=self.base_url, headers=self.get_headers(), data=json.dumps(data)
		)
		session_response_val = session_response.json()

		session_data = session_response_val.get("data", {})
		return session_data

	def end_session(self, session_id: str = None):
		"""
		Close a Kosma Session
		"""
		requests.delete(
			url=self.base_url + session_id,
			headers=self.access.get_headers(),
		)
		# frappe.db.set_value("Klarna Kosma Session", session_id_short, "status", "Closed")
		# frappe.db.commit()

	def get_session(self, session_id: str):
		session_data_response = requests.get(
			url=f"{self.base_url}{session_id}", headers=self.access.get_headers()
		)
		session_data_response.raise_for_status()
		session_data = session_data_response.json().get("data", {})

		# bank_data = session_data.get("data", {}).get("bank", {})
		# bank_name = add_bank(bank_data)

		return session_data

	def get_consent(self, session_id: str):
		"""
		Get bank consent token after successful flow and store in Bank.
		"""
		consent_url = f"{self.base_url}{session_id}/consent/get"
		consent_response = requests.post(
			url=consent_url,
			headers=self._get_headers(content_type="application/json;charset=utf-8"),
		)
		consent_response.raise_for_status()

		consent_response_val = consent_response.json()
		consent_data = consent_response_val.get("data")

		consent = {
			"consent_id": consent_data.get("consent_id"),
			"consent_token": consent_data.get("consent_token"),
			"consent_expiry": add_days(get_datetime(), 90),
		}

		# # Required to encrypt token
		# bank_doc = frappe.get_doc("Bank", bank_name)
		# bank_doc.update(consent)
		# bank_doc.save()
		return consent


# def _create_session_doc(self, session_data: Dict, session_config: Dict) -> None:
# 	session_doc = frappe.get_doc(
# 		{
# 			"doctype": "Klarna Kosma Session",
# 			"session_id_short": session_data.get("session_id_short"),
# 			"session_id": session_data.get("session_id"),
# 			"session_config": json.dumps(session_config),
# 			"status": "Running",
# 		}
# 	)
# 	session_doc.insert()


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
# 				headers=self.access.get_headers(content_type="application/json;charset=utf-8"),
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
