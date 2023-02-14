# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
from typing import Dict, Optional, Union

from erpnext.accounts.utils import get_fiscal_year
from frappe.utils import add_days, formatdate, nowdate


class KosmaError(Exception):
	"""
	Exception raised for errors while accessing Klarna Kosma endpoints.
	"""

	def __init__(self, msg: str):
		self.message = msg


class KlarnaKosmaConnector:
	def __init__(
		self,
		env: str,
		api_token: str,
		user_agent: Optional[str] = None,
		ip_address: Optional[str] = None,
	) -> None:
		is_playground = "playground." if env == "Playground" else ""
		kosma_domain = f"api.openbanking.{is_playground}klarna.com"

		self.api_token = api_token
		self.user_agent = user_agent
		self.ip_address = ip_address
		self.base_url = f"https://{kosma_domain}/xs2a/v1/sessions/"
		self.base_consent_url = f"https://{kosma_domain}/xs2a/v1/consents/"

		self.get_headers = self._get_headers
		self.get_date_range = self._get_session_flow_date_range

	def _get_headers(self, content_type: str = None) -> Dict:
		return {
			"Content-Type": content_type or "application/json",
			"Authorization": "Token {0}".format(self.api_token),
		}

	def _get_session_flow_date_range(self, from_date, to_date) -> Dict:
		current_fiscal_year = get_fiscal_year(nowdate(), as_dict=True)
		start_date = from_date or current_fiscal_year.year_start_date
		to_date = to_date or add_days(nowdate(), 90)

		return {
			"from_date": formatdate(start_date, "YYYY-MM-dd"),
			"to_date": formatdate(to_date, "YYYY-MM-dd"),
		}

	def raise_for_status(self, response: Dict) -> Union["KosmaError", None]:
		if not response.get("error"):
			return

		explanation = response.get("error").get("errors", [])
		if explanation:
			message = explanation[0]
			message = f"{message.get('location')}: {message.get('message')}"
		else:
			message = response.get("error").get("message")

		raise KosmaError(message)

	def add_psu(self, payload: dict) -> None:
		if self.user_agent and self.ip_address:
			payload["psu"] = {
				"ip_address": self.ip_address,
				"user_agent": self.user_agent,
			}
