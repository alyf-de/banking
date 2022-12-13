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

		session_id_short = session_details.get("session_id_short")
		flows = session_details.get("flows")

		flow_data = self._start_flow(
			current_flow, session_id_short=session_id_short, flows=flows
		)

		session_data = {
			"session_id_short": session_id_short,
			"client_token": flow_data.get("client_token"),
		}

		return session_data

	def fetch_accounts(self, session_id_short: str):
		"""
		Fetch Accounts using Flow API
		"""
		try:
			session_id, flow_id = get_session_flow_ids(session_id_short)

			flow_response = requests.get(
				url=self.base_url + "{0}/flows/{1}".format(session_id, flow_id),
				headers=self._get_headers(),
			)
			flow_response.raise_for_status()
			flow_response_val = flow_response.json()

			flow_state = flow_response_val.get("data").get("state")
			frappe.db.set_value(
				"Klarna Kosma Session", session_id_short, "flow_state", flow_state
			)

			self._get_set_consent_token(session_id)

			return flow_response_val
		except Exception:
			self._handle_exception(_("Failed to get Bank Accounts."))
		finally:
			self._end_session(session_id, session_id_short)

	def fetch_transactions(
		self, account_data: Dict, start_date: str, session_id_short: str
	):
		"""
		Fetch Transactions using Flow API and insert records after each page (Results could be paginated)
		"""
		# TODO: CHECK IF WORKING (shows server issue currently), handle 'incomplete: true' in response
		next_page = True
		to_date = formatdate(today(), "YYYY-MM-dd")

		session_id, flow_id = get_session_flow_ids(session_id_short)
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
				transactions_resp = requests.get(
					url=flow_url,
					headers=self._get_headers(content_type="application/json;charset=utf-8"),
					data=json.dumps(data),
				)
				transactions_resp.raise_for_status()
				transactions_val = transactions_resp.json()

				# Process Request Response
				flow_state = transactions_val.get("data").get("state")
				frappe.db.set_value(
					"Klarna Kosma Session", session_id_short, "flow_state", flow_state
				)

				self._get_set_consent_token(session_id)

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
			self._handle_exception(_("Failed to get Bank Transactions."))
		finally:
			self._end_session(session_id, session_id_short)

	def _start_session(self):
		"""
		Start a Kosma Session and return session details
		"""
		# TODO: fetch public IP, user agent
		data = {"psu": self.psu}
		dates = {
			"from_date": "2019-01-01",
			"to_date": add_days(nowdate(), 90),
		}  # TODO: fetch date from fiscal year

		if self.consent_needed:
			data["consent_scope"] = {
				"lifetime": 90,
				"accounts": dates,
				"transactions": dates,
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
		flow_link = flows.get(current_flow)  # URL
		if not flow_link:
			frappe.throw(_(f"{current_flow.title()} Flow is not available"))

		data = {}
		if current_flow == "transactions":
			data = {
				"from_date": "2020-01-01",  # TODO: fetch date from fiscal year
				"to_date": formatdate(today(), "YYYY-MM-dd"),
			}

		try:
			flow_response = requests.put(
				url=flow_link, headers=self._get_headers(), data=json.dumps(data)
			)
			flow_response.raise_for_status()
			flow_response_data = flow_response.json().get("data", {})

			# Update Flow info in Session Doc
			frappe.db.set_value(
				"Klarna Kosma Session",
				session_id_short,
				{
					"flow_id": flow_response_data.get("flow_id"),
					"flow_state": flow_response_data.get("state"),
				},
			)
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


@frappe.whitelist()
def sync_transactions(account: str, session_id_short: str):
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
	kosma.fetch_transactions(account_data, start_date, session_id_short)
