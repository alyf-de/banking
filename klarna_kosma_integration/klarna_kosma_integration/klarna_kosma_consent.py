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
from klarna_kosma_integration.klarna_kosma_integration.kosma_account import KosmaAccount
from klarna_kosma_integration.klarna_kosma_integration.kosma_transaction import (
	KosmaTransaction,
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

	def fetch_transactions(self, account: str, start_date: str):
		"""
		Fetch Transactions using Consent API and insert records after each page (Results could be paginated)
		"""
		next_page = True
		settings = frappe.get_single("Klarna Kosma Settings")
		consent_url = f"{self.base_consent_url}{self.settings.consent_id}/transactions/get"

		data = KosmaTransaction.payload(account, start_date)
		data.update({"consent_token": settings.consent_token, "psu": self.psu})

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
				transaction = KosmaTransaction(transactions_val)
				next_page = transaction.is_next_page()
				if next_page:
					consent_url, data = transaction.next_page_request()
					settings.reload()
					data.update({"consent_token": settings.consent_token, "psu": self.psu})

				if transaction.transaction_list:
					create_bank_transactions(account, transaction.transaction_list)

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
	start_date = KosmaAccount.last_sync_date(account)

	kosma = KlarnaKosmaConsent()
	kosma.fetch_transactions(account, start_date)
