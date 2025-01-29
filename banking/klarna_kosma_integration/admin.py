# Copyright (c) 2023, ALYF GmbH and contributors
# For license information, please see license.txt
import frappe

from banking.connectors.admin_request import AdminRequest
from banking.klarna_kosma_integration.exception_handler import ExceptionHandler
from banking.klarna_kosma_integration.utils import get_current_ip


class Admin:
	"""A class that directly communicates with the Banking Admin App."""

	def __init__(self, settings=None) -> None:
		"""Initialize the Admin class with the necessary settings.

		:param settings: Banking Settings document. Enables you to pass the most recent settings that may not be in the database yet.
		"""
		self.ip_address = get_current_ip()
		self.user_agent = frappe.get_request_header("User-Agent") if frappe.request else None

		settings = settings or frappe.get_single("Banking Settings")
		self.api_token = settings.get_password("api_token")
		self.customer_id = settings.customer_id
		self.url = settings.admin_endpoint + "/api/method/"

	@property
	def request(self):
		return AdminRequest(
			ip_address=self.ip_address,
			user_agent=self.user_agent,
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
