# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json

import frappe
import requests

from frappe import _
from frappe.utils import formatdate, today

from klarna_kosma_integration.klarna_kosma_integration.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from klarna_kosma_integration.klarna_kosma_integration.utils import (
	create_bank_transactions,
	to_json,
)


class KlarnaKosmaConsent(KlarnaKosmaConnector):
	def __init__(self) -> None:
		super(KlarnaKosmaConsent, self).__init__()

		if self.consent_needed:
			frappe.throw(_("The Consent Token has expired or is not available"))

	def fetch_accounts(self):
		"""
		Fetch Accounts using Consent API
		"""
		try:
			data = {"consent_token": self.settings.consent_token, "psu": self.psu}

			consent_url = f"{self.base_consent_url}{self.settings.consent_id}/accounts/get"

			accounts_response = requests.post(
				url=consent_url,
				headers=self._get_headers(content_type="application/json;charset=utf-8"),
				data=json.dumps(data),
			)

			accounts_response_val = to_json(accounts_response)
			self._exchange_consent_token(accounts_response_val)
			accounts_response.raise_for_status()

			return accounts_response_val
		except Exception:
			self._handle_exception(_("Failed to get Bank Accounts."))

	def fetch_transactions(self, account: str, account_id: str, start_date: str):
		"""
		Fetch Transactions using Consent API and insert records after each page (Results could be paginated)
		"""
		next_page = True
		to_date = formatdate(today(), "YYYY-MM-dd")
		consent_url = f"{self.base_consent_url}{self.settings.consent_id}/transactions/get"
		settings = frappe.get_single("Klarna Kosma Settings")

		data = {
			"consent_token": settings.consent_token,
			"account_id": account_id,
			"from_date": start_date,
			"to_date": to_date,
			"preferred_pagination_size": 1000,
			"psu": self.psu,
		}

		try:
			while next_page:
				transactions_resp = requests.post(  # API Call
					url=consent_url,
					headers=self._get_headers(content_type="application/json;charset=utf-8"),
					data=json.dumps(data),
				)

				transactions_val = to_json(transactions_resp)
				self._exchange_consent_token(transactions_val)
				transactions_resp.raise_for_status()

				# Process Request Response
				result = transactions_val.get("data", {}).get("result", {})

				pagination = result.get("pagination", {})
				next_page = bool(pagination and pagination.get("next"))

				# prep for next call
				if next_page:
					consent_url = pagination.get("url")
					settings.reload()
					data = {
						"consent_token": settings.consent_token,
						"offset": pagination.get("next").get("offset"),
						"psu": self.psu,
					}

				if result.get("transactions"):
					create_bank_transactions(account, result.get("transactions"))

		except Exception:
			self._handle_exception(_("Failed to get Bank Transactions."))

	def _exchange_consent_token(self, response):
		if not response:
			return

		if response.get("error"):
			new_consent_token = response.get("consent_token")
		else:
			new_consent_token = response.get("data", {}).get("consent_token")

		if new_consent_token:
			frappe.db.set_single_value(
				"Klarna Kosma Settings", {"consent_token": new_consent_token}
			)


@frappe.whitelist()
def sync_transactions(account: str):
	last_sync_date, account_id = frappe.db.get_value(
		"Bank Account", account, ["last_integration_date", "kosma_account_id"]
	)
	if last_sync_date:
		start_date = formatdate(last_sync_date, "YYYY-MM-dd")
	else:
		start_date = "2020-01-01"  # TODO: fetch date from fiscal year
		# formatdate("2022-04-01", "YYYY-MM-dd")

	kosma = KlarnaKosmaConsent()
	kosma.fetch_transactions(account, account_id, start_date)
