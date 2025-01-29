# Copyright (c) 2023, ALYF GmbH and contributors
# For license information, please see license.txt
import json
import requests


class AdminRequest:
	def __init__(
		self,
		ip_address: str,
		user_agent: str,
		api_token: str,
		url: str,
		customer_id: str,
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

	def fetch_subscription(self):
		method = "banking_admin.api.fetch_subscription_details"
		return requests.post(
			url=self.url + method, headers=self.headers, data=json.dumps(self.data)
		)

	def get_customer_portal(self):
		method = "banking_admin.api.get_customer_portal"
		return requests.get(url=self.url + method)

	def get_fintech_license(self):
		method = "banking_admin.ebics_api.get_fintech_license"
		return requests.post(
			url=self.url + method, headers=self.headers, json=self.data.copy()
		)

	def register_ebics_user(self, host_id: str, partner_id: str, user_id: str):
		data = self.data
		data.update({"host_id": host_id, "partner_id": partner_id, "user_id": user_id})
		method = "banking_admin.ebics_api.register_ebics_user"
		return requests.post(
			url=self.url + method,
			headers=self.headers,
			json=data,
		)

	def remove_ebics_user(self, host_id: str, partner_id: str, user_id: str):
		data = self.data
		data.update({"host_id": host_id, "partner_id": partner_id, "user_id": user_id})
		method = "banking_admin.ebics_api.remove_ebics_user"
		return requests.post(
			url=self.url + method,
			headers=self.headers,
			json=data,
		)
