# Copyright (c) 2023, ALYF GmbH and contributors
# For license information, please see license.txt
import requests


class AdminRequest:
	def __init__(
		self,
		api_token: str,
		url: str,
		customer_id: str,
	) -> None:
		self.api_token = api_token
		self.base_url = url
		self.customer_id = customer_id

	def request(self, method: str, endpoint: str, data: dict | None = None):
		return requests.request(
			method=method,
			url=f"{self.base_url}/api/method/{endpoint}",
			headers={
				"Alyf-Banking-Authorization": f"Token {self.api_token}",
				"Alyf-Customer-Id": self.customer_id,
			},
			json=data,
		)

	def fetch_subscription(self):
		return self.request("GET", "banking_admin.api.fetch_subscription_details")

	def get_customer_portal(self):
		return self.request("GET", "banking_admin.api.get_customer_portal")

	def get_fintech_license(self):
		return self.request("GET", "banking_admin.ebics_api.get_fintech_license")

	def register_ebics_user(
		self, host_id: str, partner_id: str, user_id: str, remove: bool = False
	):
		if remove:
			endpoint = "banking_admin.ebics_api.remove_ebics_user"
		else:
			endpoint = "banking_admin.ebics_api.register_ebics_user"

		return self.request(
			"POST",
			endpoint,
			{"host_id": host_id, "partner_id": partner_id, "user_id": user_id},
		)
