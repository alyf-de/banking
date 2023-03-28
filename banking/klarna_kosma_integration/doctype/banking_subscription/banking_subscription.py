# Copyright (c) 2023, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
import uuid
from frappe.model.document import Document


class BankingSubscription(Document):
	@frappe.whitelist()
	def ensure_customer_id(self):
		if not self.customer_id:
			self.db_set("customer_id", str(uuid.uuid4()))


def update_subscription():
	import requests

	customer_id = frappe.db.get_single_value("Banking Subscription", "customer_id")
	if not customer_id:
		frappe.db.set_single_value("Banking Subscription", "active_until", "None")
		return

	# Ask our backend for the subscription status
	# TODO: Implement this endpoint
	r = requests.get(f"https://banking.alyf.de/customer/{customer_id}")
	r.raise_for_status()
	data = r.json()
	frappe.db.set_single_value(
		"Banking Subscription", "active_until", data["active_until"]
	)
	frappe.db.set_single_value(
		"Banking Subscription", "max_transactions", data["max_transactions"]
	)
