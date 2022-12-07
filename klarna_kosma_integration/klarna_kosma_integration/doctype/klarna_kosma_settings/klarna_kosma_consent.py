# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json

import frappe
import requests

from frappe import _
from frappe.utils import add_days, nowdate

from klarna_kosma_integration.klarna_kosma_integration.doctype.klarna_kosma_settings.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)


class KlarnaKosmaConsent(KlarnaKosmaConnector):
	def __init__(self) -> None:
		super(KlarnaKosmaConsent, self).__init__()

		if self.consent_needed:
			frappe.throw(_("The Consent Token has expired or is not available"))

	def fetch_accounts(self):
		data = {
			"consent_token": self.settings.consent_token,
			"psu": {"ip_address": "49.36.101.156", "user_agent": "any"},
		}

		consent_url = f"{self.base_consent_url}{self.settings.consent_id}/accounts/get"

		accounts_response = requests.post(
			url=consent_url,
			headers=self._get_headers(content_type="application/json;charset=utf-8"),
			data=json.dumps(data),
		)
		accounts_response_val = accounts_response.json()
		self._exchange_consent_token(accounts_response_val)

		if accounts_response.status_code >= 400:
			error = accounts_response_val.get("error")
			frappe.throw(_(str(error.get("code")) + ": " + error.get("message")))
		else:
			return accounts_response_val

	def sync_transactions(self):
		# first call with consent base url, following calls with link in response with offset
		pass

	def _exchange_consent_token(self, response):
		new_consent_token = response.get("consent_token") or response.get("data").get(
			"consent_token"
		)
		if new_consent_token:
			frappe.db.set_single_value(
				"Klarna Kosma Settings", {"consent_token": new_consent_token}
			)
