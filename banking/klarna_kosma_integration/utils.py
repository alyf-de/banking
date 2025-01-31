# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
from typing import Optional
from banking.klarna_kosma_integration.exception_handler import ExceptionHandler

import frappe
import requests


def get_current_ip() -> Optional[str]:
	"""Return the current IP or `None`.

	- If run outside of a request context, return `None` (e.g. in a background job).
	- If run on localhost, return the public IP address as queried from AWS checkip.
	"""
	if not frappe.request:
		return None

	ip_address = frappe.local.request_ip
	if ip_address == "127.0.0.1":
		try:
			ip_address = requests.get("https://checkip.amazonaws.com", timeout=3).text.strip()
		except Exception as exc:
			ExceptionHandler(exc)

	return ip_address
