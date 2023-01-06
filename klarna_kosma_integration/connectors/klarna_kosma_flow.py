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
	def __init__(self, env: str, api_token: str) -> None:
		super(KlarnaKosmaFlow, self).__init__(env, api_token)

	def start(self, flows: Dict, flow_type: str) -> Dict:
		"""
		Start flow > Generate & return flow data including Client Token
		"""
		data = {}
		flow_link = flows.get(flow_type, "")

		if flow_type == "accounts":
			data.update(self.get_date_range(is_flow=True))

		flow_response = requests.put(
			url=flow_link, headers=self.get_headers(), data=json.dumps(data)
		)
		flow_response_data = flow_response.json().get("data", {})
		return flow_response_data

	def accounts(self, session_id: str, flow_id: str) -> Dict:
		"""
		- Fetch Accounts using Flow API
		- Create Bank Record from Session Bank data (better UX, less user interaction)
		- Set consent token in Bank record
		"""
		flow_response = requests.get(
			url=f"{self.base_url}{session_id}/flows/{flow_id}",
			headers=self.get_headers(),
		)
		flow_response_val = flow_response.json().get("data", {})

		return flow_response_val

	def start_session(self) -> Dict:
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
		session_data["consent_scope"] = data.get("consent_scope")
		return session_data

	def end_session(self, session_id: str = None) -> None:
		"""
		Close a Kosma Session
		"""
		requests.delete(
			url=self.base_url + session_id,
			headers=self.get_headers(),
		)

	def get_session(self, session_id: str) -> Dict:
		"""Returns current session's data e.g. bank, current flow, session ID, etc."""

		session_data_response = requests.get(
			url=f"{self.base_url}{session_id}", headers=self.get_headers()
		)
		session_data = session_data_response.json().get("data", {})

		return session_data

	def get_consent(self, session_id: str) -> Dict:
		"""
		Get bank consent token after successful flow.
		"""
		consent_url = f"{self.base_url}{session_id}/consent/get"
		consent_response = requests.post(
			url=consent_url,
			headers=self._get_headers(content_type="application/json;charset=utf-8"),
		)

		consent_response_val = consent_response.json()
		consent_data = consent_response_val.get("data", {})

		consent = {
			"consent_id": consent_data.get("consent_id"),
			"consent_token": consent_data.get("consent_token"),
			"consent_expiry": add_days(get_datetime(), 90),
		}

		return consent
