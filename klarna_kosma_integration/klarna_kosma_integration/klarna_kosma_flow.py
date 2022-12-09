# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict

import frappe
import requests

from frappe import _
from frappe.utils import add_days, formatdate, nowdate, today

from klarna_kosma_integration.klarna_kosma_integration.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from klarna_kosma_integration.klarna_kosma_integration.utils import (
	create_bank_transactions,
)


class KlarnaKosmaFlow(KlarnaKosmaConnector):
	def __init__(self) -> None:
		super(KlarnaKosmaFlow, self).__init__()

	def get_client_token(self, current_flow):
		"""
		Get Client Token to render XS2A App
		"""
		session_details = self._start_session()
		session_data = {"session_id": session_details.get("session_id")}

		flows = session_details.get("flows")
		flow_data = self._start_flow_in_session(current_flow, flows=flows)

		session_data.update(
			{
				"client_token": flow_data.get("data").get("client_token"),
				"flow_id": flow_data.get("data").get("flow_id"),
				"flow_state": flow_data.get("data").get("state"),
			}
		)
		return session_data

	def fetch_accounts(self, session_id, flow_id):
		"""
		Fetch Accounts using Flow API
		"""
		try:
			flow_response = requests.get(
				url=self.base_url + "{0}/flows/{1}".format(session_id, flow_id),
				headers=self._get_headers(),
			)
			flow_response_val = flow_response.json()

			if flow_response.status_code >= 400:
				error = flow_response_val.get("error")
				frappe.throw(_(str(error.get("code")) + ": " + error.get("message")))
			else:
				self._get_consent_token(session_id)
				return flow_response_val
		except Exception:
			frappe.throw(_("Failed to get Kosma flow data"))
		finally:
			self._end_session(session_id)

	def fetch_transactions(
		self, account_data: Dict, start_date: str, session_id: str, flow_id: str
	):
		"""
		Fetch Transactions using Flow API and insert records after each page (Results could be paginated)
		"""
		# TODO: CHECK IF WORKING (shows server issue currently), handle 'incomplete: true' in response
		next_page = True
		to_date = formatdate(today(), "YYYY-MM-dd")
		flow_url = f"{self.base_url}{session_id}/flows/{flow_id}"

		data = {
			"account_id": account_data.get("account_id"),
			"account_number": account_data.get("account_no"),
			"from_date": start_date,
			"to_date": to_date,
			"preferred_pagination_size": 1000,
		}

		try:
			while next_page:
				transactions_resp = requests.get(  # API Call
					url=flow_url,
					headers=self._get_headers(content_type="application/json;charset=utf-8"),
					data=json.dumps(data),
				)
				transactions_val = transactions_resp.json()

				# Process Request Response
				if transactions_resp.status_code >= 400:
					error = transactions_val.get("error")
					frappe.throw(_(str(error.get("code")) + ": " + error.get("message")))
				else:
					self._get_consent_token(session_id)
					result = transactions_val.get("data", {}).get("result", {})

					pagination = result.get("pagination", {})
					next_page = bool(pagination and pagination.get("next"))

					# prep for next call
					if next_page:
						flow_url = pagination.get("url")
						data = {"offset": pagination.get("next").get("offset")}

					if result.get("transactions", {}):
						create_bank_transactions(account_data.get("account"), result.get("transactions"))
		except Exception:
			frappe.throw(_("Failed to get Kosma transaction data"))
		finally:
			self._end_session(session_id)

	def _start_session(self):
		"""
		Start a Kosma Session and return session details
		"""
		# TODO: fetch public IP, user agent
		data = {"psu": {"ip_address": "49.36.101.156", "user_agent": "any"}}

		if self.consent_needed:
			data["consent_scope"] = {
				"lifetime": 90,
				"accounts": {
					"from_date": "2019-01-01",  # TODO: fetch date from fiscal year
					"to_date": add_days(nowdate(), 90),
				},
				"transactions": {
					"from_date": "2019-01-01",  # TODO: fetch date from fiscal year
					"to_date": add_days(nowdate(), 90),
				},
			}

		try:
			session_response = requests.put(
				url=self.base_url, headers=self._get_headers(), data=json.dumps(data)
			)
			session_response_val = session_response.json()

			if session_response.status_code >= 400:
				error = session_response_val.get("error")
				frappe.throw(_(str(error.get("code")) + ": " + error.get("message")))

			return session_response_val.get("data")

		except Exception:
			frappe.throw(_("Failed to start Kosma session"))

	def _start_flow_in_session(self, current_flow: str, flows: Dict[str, str] = None):
		"""
		Start flow > generate & return Client Token
		"""
		flow_link = flows.get(current_flow)  # URL

		if not flow_link:
			frappe.throw(_(f"{current_flow.title()} Flow is not available"))

		data = {}
		if current_flow == "transactions":
			data = {
				"from_date": "2020-01-01",  # TODO: fetch date from fiscal year
				"to_date": formatdate(today(), "YYYY-MM-dd"),
			}

		flow_response = requests.put(
			url=flow_link, headers=self._get_headers(), data=json.dumps(data)
		).json()
		return flow_response

	def _end_session(self, session_id: str = None):
		"""
		Close a Kosma Session
		"""
		try:
			requests.delete(
				url=self.base_url + session_id,
				headers=self._get_headers(),
			)
		except Exception:
			frappe.throw(_("Failed to end Kosma session"))


@frappe.whitelist()
def sync_transactions(account: str, session_id: str, flow_id: str):
	last_sync_date, account_id, account_no = frappe.db.get_value(
		"Bank Account",
		account,
		["last_integration_date", "kosma_account_id", "bank_account_no"],
	)
	if last_sync_date:
		start_date = formatdate(last_sync_date, "YYYY-MM-dd")
	else:
		start_date = "2020-01-01"  # TODO: fetch date from fiscal year
		# formatdate("2022-04-01", "YYYY-MM-dd")

	account_data = dict(account=account, account_id=account_id, account_no=account_no)
	kosma = KlarnaKosmaFlow()
	kosma.fetch_transactions(account_data, start_date, session_id, flow_id)
