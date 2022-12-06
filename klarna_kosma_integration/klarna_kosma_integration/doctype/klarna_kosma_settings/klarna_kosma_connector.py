# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt

import json
from typing import Dict

import frappe
import requests
from frappe import _


class KlarnaKosmaConnector:
	def __init__(self) -> None:
		self.settings = frappe.get_single("Klarna Kosma Settings")
		self.api_token = self.settings.get_password("api_token")
		self.base_url = "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/"

	def get_client_token(self):
		"""
		Get Client Token to render XS2A App
		"""
		session_details = self._start_session()
		session_data = {"session_id": session_details.get("data").get("session_id")}

		flows = session_details.get("data").get("flows")
		flow_data = self._start_flow_in_session(flows=flows)

		session_data.update(
			{
				"client_token": flow_data.get("data").get("client_token"),
				"flow_id": flow_data.get("data").get("flow_id"),
				"flow_state": flow_data.get("data").get("state"),
			}
		)
		return session_data

	def execute_flow(self, session_id, flow_id):
		try:
			flow_response = requests.get(
				url=self.base_url + "{0}/flows/{1}".format(session_id, flow_id),
				headers=self._get_headers(),
			)
			flow_response_val = flow_response.json()

			if flow_response.status_code >= 400:
				error = flow_response_val.get("error")
				frappe.throw(_(str(error.get("code")) + ": " + error.get("message")))

			return flow_response_val
		except Exception:
			frappe.throw(_("Failed to get Kosma flow data"))
		finally:
			self._end_session(session_id)

	def _get_headers(self, content_type: str = None):
		return {
			"Content-Type": content_type or "application/json",
			"Authorization": "Token {0}".format(self.api_token),
		}

	def _start_session(self):
		# TODO: fetch public IP, user agent
		data = {"psu": {"ip_address": "49.36.101.156", "user_agent": "any"}}
		try:
			session_response = requests.put(
				url=self.base_url, headers=self._get_headers(), data=json.dumps(data)
			)
			session_response_val = session_response.json()

			if session_response.status_code >= 400:
				error = session_response_val.get("error")
				frappe.throw(_(str(error.get("code")) + ": " + error.get("message")))

			return session_response_val
		except Exception:
			frappe.throw(_("Failed to start Kosma session"))

	def _start_flow_in_session(self, flows: Dict[str, str] = None):
		flow_link = flows.get("accounts")  # URL

		if not flow_link:
			frappe.throw(_("An error occurred while starting a flow"))

		accounts_flow_response = requests.put(
			url=flow_link, headers=self._get_headers()
		).json()
		return accounts_flow_response

	def _end_session(self, session_id: str = None):
		try:
			requests.delete(
				url=self.base_url + session_id,
				headers=self._get_headers(),
			)
		except Exception:
			frappe.throw(_("Failed to end Kosma session"))
