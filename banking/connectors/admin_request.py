# Copyright (c) 2023, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict, Optional
import requests


class AdminRequest:
	def __init__(
		self, ip_address: str, user_agent: str, api_token: str, url: str, customer_id: str
	) -> None:
		self.ip_address = ip_address
		self.user_agent = user_agent
		self.api_token = api_token
		self.url = url
		self.customer_id = customer_id

	@property
	def headers(self):
		return {"Alyf-Banking-Authorization": f"Token {self.api_token}"}

	@property
	def data(self):
		return {
			"ip_address": self.ip_address,
			"user_agent": self.user_agent,
			"customer_id": self.customer_id,
		}

	def get_client_token(
		self,
		current_flow: str,
		account: Optional[Dict] = None,
		from_date: Optional[str] = None,
		to_date: Optional[str] = None,
		country_code: Optional[str] = None,
	):
		data = self.data
		data.update(
			{
				"current_flow": current_flow,
				"account": account,
				"from_date": from_date,
				"to_date": to_date,
				"country_code": country_code,
			}
		)

		method = "banking_admin.api.get_client_token"
		return requests.post(
			url=self.url + method, headers=self.headers, data=json.dumps(data)
		)

	def flow_accounts(self, session_id: str, flow_id: str):
		data = self.data
		data.update({"session_id": session_id, "flow_id": flow_id})

		method = "banking_admin.api.fetch_accounts_and_bank"
		return requests.post(
			url=self.url + method, headers=self.headers, data=json.dumps(data)
		)

	def flow_transactions(
		self,
		session_id: str,
		flow_id: str,
		url: Optional[str] = None,
		offset: Optional[str] = None,
	):
		data = self.data
		data.update(
			{"session_id": session_id, "flow_id": flow_id, "url": url, "offset": offset}
		)

		method = "banking_admin.api.fetch_flow_transactions"
		return requests.post(
			url=self.url + method, headers=self.headers, data=json.dumps(data)
		)

	def end_session(self, session_id: str):
		data = self.data
		data.update({"session_id": session_id})

		method = "banking_admin.api.end_session"
		requests.post(url=self.url + method, headers=self.headers, data=json.dumps(data))

	def consent_accounts(self, consent_id: str, consent_token: str):
		data = self.data
		data.update({"consent_id": consent_id, "consent_token": consent_token})

		method = "banking_admin.api.fetch_consent_accounts"
		return requests.post(
			url=self.url + method, headers=self.headers, data=json.dumps(data)
		)

	def consent_transactions(
		self,
		account_id: str,
		start_date: str,
		consent_id: str,
		consent_token: str,
		url: Optional[str] = None,
		offset: Optional[str] = None,
	):
		data = self.data
		data.update(
			{
				"account_id": account_id,
				"start_date": start_date,
				"consent_id": consent_id,
				"consent_token": consent_token,
				"url": url,
				"offset": offset,
			}
		)

		method = "banking_admin.api.fetch_consent_transactions"
		return requests.post(
			url=self.url + method, headers=self.headers, data=json.dumps(data)
		)

	def fetch_subscription(self):
		method = "banking_admin.api.fetch_subscription_details"
		return requests.post(
			url=self.url + method, headers=self.headers, data=json.dumps(self.data)
		)

	def get_customer_portal(self):
		method = "banking_admin.api.get_customer_portal"
		return requests.get(url=self.url + method)
