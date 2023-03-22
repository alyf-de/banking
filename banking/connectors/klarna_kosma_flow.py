# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict, Optional

import requests
from frappe import _
from frappe.utils import add_days, get_datetime

from banking.connectors.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from banking.klarna_kosma_integration.utils import to_json


class KlarnaKosmaFlow(KlarnaKosmaConnector):
	def __init__(
		self,
		env: str,
		api_token: str,
		user_agent: Optional[str] = None,
		ip_address: Optional[str] = None,
		from_date: Optional[str] = None,
		to_date: Optional[str] = None,
	) -> None:
		super(KlarnaKosmaFlow, self).__init__(env, api_token, user_agent, ip_address)
		self.from_date = from_date
		self.to_date = to_date

	def start(
		self,
		flows: Dict,
		flow_type: str,
		iban: Optional[str] = None,
		account_id: Optional[str] = None,
	) -> Dict:
		"""
		Start flow > Generate & return flow data including Client Token
		"""
		data = {}
		flow_link = flows.get(flow_type, "")

		if flow_type == "transactions":
			data.update({"iban": iban, "account_id": account_id})
			data.update(self.get_date_range(self.from_date, self.to_date))

		flow_response = requests.put(
			url=flow_link, headers=self.get_headers(), data=json.dumps(data)
		)

		flow_response_data = flow_response.json()
		return flow_response_data.get("data", {}) or flow_response_data

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

		flow_response_val = flow_response.json()
		return flow_response_val.get("data", {}) or flow_response_val

	def start_session(self, flow_type: str, iban: Optional[str] = None) -> Dict:
		"""
		Start a Kosma Session and return session details
		"""
		transaction_data = self.get_date_range(self.from_date, self.to_date)
		if iban:
			transaction_data["ibans"] = [iban]

		data = {"consent_scope": {"lifetime": 90, "transactions": transaction_data}}

		if flow_type == "accounts":
			# Avoid accounts scope in a transactions flow to avoid accounts fetch
			# Transactions in scope can be used for both flows
			data["consent_scope"]["accounts"] = {}

		self.add_psu(data)

		session_response = requests.put(
			url=self.base_url, headers=self.get_headers(), data=json.dumps(data)
		)
		session_response_val = session_response.json()

		session_data = session_response_val.get("data", {})
		if session_data:
			session_data["consent_scope"] = data.get("consent_scope", {})

		return session_data or session_response_val

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

		session_data = session_data_response.json()
		return session_data.get("data", {}) or session_data

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

		consent_data, consent = consent_response_val.get("data", {}), None
		if consent_data:
			consent = {
				"consent_id": consent_data.get("consent_id"),
				"consent_token": consent_data.get("consent_token"),
				"consent_expiry": add_days(get_datetime(), 90),
			}

		return consent or consent_response_val

	def transactions(
		self,
		session_id: str,
		flow_id: str,
		url: Optional[str] = None,
		offset: Optional[str] = None,
	) -> Dict:
		"""
		Fetch Transactions for a single page using Consent API
		"""
		flow_url = url or f"{self.base_url}{session_id}/flows/{flow_id}"
		data = {"offset": offset} if offset else {}

		transactions_resp = requests.get(
			url=flow_url, headers=self.get_headers(), data=json.dumps(data) if data else data
		)
		# NOTE: strange case where kosma returns a 403 if data is a stringified empty dict

		transactions_val = to_json(transactions_resp)
		return transactions_val.get("data", {}) or transactions_val
