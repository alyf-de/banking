# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
from typing import Dict
import frappe
import requests

from frappe import _
from frappe.utils import add_days, add_to_date, formatdate, get_datetime, nowdate
from erpnext.accounts.utils import get_fiscal_year


class KlarnaKosmaConnector:
	def __init__(self) -> None:
		self.settings = frappe.get_single("Klarna Kosma Settings")
		self.api_token = self.settings.get_password("api_token")

		self.base_url = "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/"
		self.base_consent_url = (
			"https://api.openbanking.playground.klarna.com/xs2a/v1/consents/"
		)

		self.psu = {  # TODO: fetch public IP, user agent
			"user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
			"ip_address": "49.36.101.156",
		}

	def _get_headers(self, content_type: str = None):
		return {
			"Content-Type": content_type or "application/json",
			"Authorization": "Token {0}".format(self.api_token),
		}

	def _set_consent_token(self, session_id: str, bank_name: str):
		"""
		Get bank consent token after successful flow and store in Bank.
		"""
		if not self.needs_consent(bank_name):
			return

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
		frappe.db.set_value("Bank", bank_name, consent)

	@staticmethod
	def needs_consent(bank: str) -> bool:
		"Returns False if there is atleast 1 hour before consent expires."
		consent_expiry = frappe.get_value("Bank", bank, "consent_expiry")
		if not consent_expiry:
			return True

		now = get_datetime()
		expiry_with_buffer = add_to_date(get_datetime(consent_expiry), hours=-1)

		return now > expiry_with_buffer

	def _handle_exception(self, error_msg: str):
		frappe.log_error(title=_("Kosma Error"), message=frappe.get_traceback())
		frappe.throw(title=_("Kosma Error"), msg=error_msg)

	def _update_flow_state(self, response_data: Dict, session_id_short: str) -> None:
		flow_state = response_data.get("data").get("state")
		frappe.db.set_value(
			"Klarna Kosma Session", session_id_short, "flow_state", flow_state
		)

	def _get_session_flow_date_range(self, is_flow: bool = False):
		# TODO: verify logic
		current_fiscal_year = get_fiscal_year(nowdate(), as_dict=True)
		start_date = current_fiscal_year.year_start_date
		return {
			"from_date": formatdate(start_date, "YYYY-MM-dd"),
			"to_date": nowdate() if is_flow else add_days(nowdate(), 90),
		}
