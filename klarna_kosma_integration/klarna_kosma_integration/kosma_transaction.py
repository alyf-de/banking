# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import frappe

from frappe.utils import formatdate, today


class KosmaTransaction:
	def __init__(self, response_value) -> None:
		self.result = response_value.get("data", {}).get("result", {})
		self.pagination = self.result.get("pagination", {})
		self.transaction_list = self.result.get("transactions", [])

	def is_next_page(self) -> bool:
		next_page = bool(self.pagination and self.pagination.get("next"))
		return next_page

	def next_page_request(self):
		flow_url = self.pagination.get("url")
		data = {"offset": self.pagination.get("next").get("offset")}
		return flow_url, data

	@staticmethod
	def payload(account: str, start_date: str, flow: bool = False):
		account_id, account_no = frappe.db.get_value(
			"Bank Account", account, ["kosma_account_id", "bank_account_no"]
		)
		payload = {
			"account_id": account_id,
			"from_date": start_date,
			"to_date": formatdate(today(), "YYYY-MM-dd"),
			"preferred_pagination_size": 1000,
		}

		if flow:
			payload.update({"account_number": account_no})

		return payload
