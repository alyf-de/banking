# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
import requests

from frappe import _
from frappe.utils import add_days, add_to_date, get_datetime, nowdate


class KlarnaKosmaConnector:
	def __init__(self) -> None:
		self.settings = frappe.get_single("Klarna Kosma Settings")

		self.api_token = self.settings.get_password("api_token")
		self.base_url = "https://api.openbanking.playground.klarna.com/xs2a/v1/sessions/"
		self.base_consent_url = (
			"https://api.openbanking.playground.klarna.com/xs2a/v1/consents/"
		)
		self.consent_needed = self._needs_consent() if self.settings.consent_expiry else True

		self.psu = {
			"user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36",
			"ip_address": "49.36.101.156",
		}

	def _get_headers(self, content_type: str = None):
		return {
			"Content-Type": content_type or "application/json",
			"Authorization": "Token {0}".format(self.api_token),
		}

	def _get_set_consent_token(self, session_id: str):
		"""
		Get consent token and store in Settings.
		"""
		if not self.consent_needed:
			return

		consent_url = f"{self.base_url}{session_id}/consent/get"
		consent_response = requests.post(
			url=consent_url,
			headers=self._get_headers(content_type="application/json;charset=utf-8"),
		)
		consent_response_val = consent_response.json()
		consent_response.raise_for_status()

		consent_data = consent_response_val.get("data")
		consent = {
			"consent_id": consent_data.get("consent_id"),
			"consent_token": consent_data.get("consent_token"),
			"consent_expiry": add_days(get_datetime(), 90),
		}
		frappe.db.set_single_value("Klarna Kosma Settings", consent)

	def _needs_consent(self):
		"Returns False if there is atleast 1 hour before consent expires."
		now = get_datetime()
		consent_expiry = get_datetime(self.settings.consent_expiry)
		expiry_with_buffer = add_to_date(consent_expiry, hours=-1)

		return now > expiry_with_buffer

	def _handle_exception(self, error_msg: str):
		frappe.log_error(title=_("Kosma Error"), message=frappe.get_traceback())
		frappe.throw(title=_("Kosma Error"), msg=error_msg)
