# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict

import frappe
import requests

from frappe import _

from klarna_kosma_integration.connectors.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from klarna_kosma_integration.connectors.kosma_account import KosmaAccount
from klarna_kosma_integration.connectors.kosma_transaction import (
	KosmaTransaction,
)
from klarna_kosma_integration.klarna_kosma_integration.utils import (
	create_bank_transactions,
	get_account_name,
	to_json,
	update_account,
)


class KlarnaKosmaConsent(KlarnaKosmaConnector):
	def __init__(self) -> None:
		super(KlarnaKosmaConsent, self).__init__()

	def accounts(self, consent_id: str, consent_token: str):
		"""
		Fetch Accounts for a Bank using Consent API
		"""
		try:
			data = {"consent_token": consent_token, "psu": self.access.psu}
			consent_url = f"{self.access.base_consent_url}{consent_id}/accounts/get"

			accounts_response = requests.post(
				url=consent_url,
				headers=self.access.get_headers(content_type="application/json;charset=utf-8"),
				data=json.dumps(data),
			)

			accounts_response_val = to_json(accounts_response)
			# self._exchange_consent_token(accounts_response_val, bank_name)
			accounts_response.raise_for_status()

			return accounts_response_val
		except Exception:
			self._handle_exception(_("Failed to get Bank Accounts."))

	def transactions(self, account: str, start_date: str):
		"""
		Fetch Transactions using Consent API and insert records after each page (Results could be paginated)
		"""
		bank_name = frappe.db.get_value("Bank Account", account, "bank")
		consent_id, consent_token = self._get_consent_data(bank_name)

		next_page = True
		consent_url = f"{self.base_consent_url}{consent_id}/transactions/get"

		data = KosmaTransaction.payload(account, start_date)
		data.update({"consent_token": consent_token, "psu": self.psu})

		try:
			while next_page:
				transactions_resp = requests.post(  # API Call
					url=consent_url,
					headers=self._get_headers(content_type="application/json;charset=utf-8"),
					data=json.dumps(data),
				)

				# Error response may have consent token. Raise error after exchange
				transactions_val = to_json(transactions_resp)
				new_consent_token = self._exchange_consent_token(transactions_val, bank_name)
				transactions_resp.raise_for_status()

				# Process Request Response
				transaction = KosmaTransaction(transactions_val)
				next_page = transaction.is_next_page()
				if next_page:
					consent_url, data = transaction.next_page_request()
					data.update({"consent_token": new_consent_token, "psu": self.psu})

				if transaction.transaction_list:
					create_bank_transactions(account, transaction.transaction_list)

		except Exception:
			self._handle_exception(_("Failed to get Bank Transactions."))

	# def _exchange_consent_token(self, response: dict, bank: str):
	# 	if (not response) or (not isinstance(response, dict)):
	# 		return

	# 	if response.get("error"):
	# 		new_consent_token = response.get("consent_token")
	# 	else:
	# 		new_consent_token = response.get("data", {}).get("consent_token")

	# 	if new_consent_token:
	# 		bank_doc = frappe.get_doc("Bank", bank)
	# 		bank_doc.consent_token = new_consent_token
	# 		bank_doc.save()
	# 		frappe.db.commit()

	# 	return new_consent_token

	# def _get_consent_data(self, bank_name):
	# 	"""Get stored bank consent."""
	# 	if self.needs_consent(bank_name):
	# 		frappe.throw(
	# 			_("The Consent Token has expired/is unavailable for Bank {0}.").format(
	# 				frappe.bold(bank_name)
	# 			)
	# 		)

	# 	bank_doc = frappe.get_doc("Bank", bank_name)
	# 	return bank_doc.consent_id, bank_doc.get_password("consent_token")


@frappe.whitelist()
def sync_transactions(account: str):
	start_date = KosmaAccount.last_sync_date(account)

	kosma = KlarnaKosmaConsent()
	kosma.fetch_transactions(account, start_date)


@frappe.whitelist()
def sync_all_accounts_and_transactions():
	"""
	Refresh all Bank accounts and enqueue their transactions sync.
	"""
	banks = frappe.get_all("Bank", filters={"consent_id": ["is", "set"]}, pluck="name")
	kosma = KlarnaKosmaConsent()

	# Update all bank accounts
	accounts_list = []
	for bank in banks:
		accounts = kosma.fetch_accounts(bank)
		accounts = accounts.get("data", {}).get("result", {}).get("accounts")

		for account in accounts:
			account_name = get_account_name(account)
			bank_account_name = "{} - {}".format(account_name, bank)

			if not frappe.db.exists("Bank Account", bank_account_name):
				continue

			update_account(account, bank_account_name)
			accounts_list.append(bank_account_name)  # list of legitimate bank account names

	for bank_account in accounts_list:
		frappe.enqueue(sync_transactions, account=bank_account)
