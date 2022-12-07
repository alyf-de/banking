# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict

import frappe
import requests

from frappe import _
from frappe.utils import add_days, nowdate

from klarna_kosma_integration.klarna_kosma_integration.doctype.klarna_kosma_settings.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)


class KlarnaKosmaFlow(KlarnaKosmaConnector):
	def __init__(self) -> None:
		super(KlarnaKosmaFlow, self).__init__()

	def get_client_token(self):
		"""
		Get Client Token to render XS2A App
		"""
		session_details = self._start_session()
		session_data = {"session_id": session_details.get("session_id")}

		flows = session_details.get("flows")
		flow_data = self._start_flow_in_session(flows=flows)

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

	def sync_transactions(self):
		pass

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
					"from_date": "2022-04-01",  # TODO: fetch date from fiscal year
					"to_date": add_days(nowdate(), 90),
				},
				"transactions": {
					"from_date": "2022-04-01",  # TODO: fetch date from fiscal year
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

	def _start_flow_in_session(self, flows: Dict[str, str] = None):
		"""
		Start flow > generate & return Client Token
		"""
		flow_link = flows.get("accounts")  # URL

		if not flow_link:
			frappe.throw(_("Accounts flow is prohibited"))

		accounts_flow_response = requests.put(
			url=flow_link, headers=self._get_headers()
		).json()

		return accounts_flow_response

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
