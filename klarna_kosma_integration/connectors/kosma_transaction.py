# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
from typing import Dict

from frappe.utils import formatdate, today


class KosmaTransaction:
	def __init__(self, response_value) -> None:
		self.result = response_value.get("result", {})
		self.pagination = self.result.get("pagination", {})
		self.transaction_list = self.result.get("transactions", [])

	def is_next_page(self) -> bool:
		next_page = bool(self.pagination and self.pagination.get("next"))
		return next_page

	def next_page_request(self):
		url = self.pagination.get("url")
		offset = self.pagination.get("next").get("offset")
		return url, offset

	@staticmethod
	def payload(account_id: str, start_date: str) -> Dict:
		payload = {
			"account_id": account_id,
			"from_date": start_date,
			"to_date": formatdate(today(), "YYYY-MM-dd"),
			"preferred_pagination_size": 1000,
		}

		return payload
