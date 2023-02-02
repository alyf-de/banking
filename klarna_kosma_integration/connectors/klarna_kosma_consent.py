# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict, Optional

import requests
from klarna_kosma_integration.connectors.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from klarna_kosma_integration.connectors.kosma_transaction import KosmaTransaction
from klarna_kosma_integration.klarna_kosma_integration.utils import to_json


class KlarnaKosmaConsent(KlarnaKosmaConnector):
	def __init__(
		self,
		env: str,
		api_token: str,
		user_agent: Optional[str] = None,
		ip_address: Optional[str] = None,
	) -> None:
		super(KlarnaKosmaConsent, self).__init__(env, api_token, user_agent, ip_address)

	def accounts(self, consent_id: str, consent_token: str) -> Dict:
		"""
		Fetch Accounts for a Bank using Consent API
		"""
		data = {"consent_token": consent_token}
		self.add_psu(data)
		consent_url = f"{self.base_consent_url}{consent_id}/accounts/get"

		accounts_response = requests.post(
			url=consent_url,
			headers=self.get_headers(content_type="application/json;charset=utf-8"),
			data=json.dumps(data),
		)

		accounts_response_val = to_json(accounts_response)
		return accounts_response_val.get("data", {}) or accounts_response_val

	def transactions(
		self,
		account_id: str,
		start_date: str,
		consent_id: str,
		consent_token: str,
		url: Optional[str],
		offset: Optional[str],
	) -> Dict:
		"""
		Fetch Transactions using Consent API and insert records after each page (Results could be paginated)
		"""
		consent_url = url or f"{self.base_consent_url}{consent_id}/transactions/get"

		data = KosmaTransaction.payload(account_id, start_date)
		self.add_psu(data)
		data["consent_token"] = consent_token
		if offset:
			data["offset"] = offset

		transactions_resp = requests.post(  # API Call
			url=consent_url,
			headers=self.get_headers(content_type="application/json;charset=utf-8"),
			data=json.dumps(data),
		)

		# Error response may have consent token. Raise error after exchange
		transactions_val = to_json(transactions_resp)

		return transactions_val.get("data", {}) or transactions_val
