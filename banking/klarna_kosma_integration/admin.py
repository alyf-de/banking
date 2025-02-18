# Copyright (c) 2023, ALYF GmbH and contributors
# For license information, please see license.txt
import frappe

from banking.connectors.admin_request import AdminRequest
from banking.klarna_kosma_integration.exception_handler import ExceptionHandler


class Admin:
	"""A class that directly communicates with the Banking Admin App."""

	def __init__(self, settings=None) -> None:
		"""Initialize the Admin class with the necessary settings.

		:param settings: Banking Settings document. Enables you to pass the most recent settings that may not be in the database yet.
		"""
		settings = settings or frappe.get_single("Banking Settings")
		self.api_token = settings.get_password("api_token")
		self.customer_id = settings.customer_id
		self.url = settings.admin_endpoint

	@property
	def request(self):
		return AdminRequest(
			api_token=self.api_token,
			url=self.url,
			customer_id=self.customer_id,
		)

	def fetch_subscription(self):
		try:
			subscription = self.request.fetch_subscription()
			subscription.raise_for_status()
			return subscription.json().get("message", {})
		except Exception as exc:
			ExceptionHandler(exc)

	def get_customer_portal_url(self):
		try:
			url = self.request.get_customer_portal()
			url.raise_for_status()
			return url.json().get("message")
		except Exception as exc:
			ExceptionHandler(exc)
