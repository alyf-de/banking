# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import frappe

from frappe.utils import formatdate, nowdate
from erpnext.accounts.utils import get_fiscal_year


class KosmaAccount:
	@staticmethod
	def last_sync_date(account_name: str):
		# TODO: verify logic
		last_sync_date = frappe.db.get_value(
			"Bank Account", account_name, "last_integration_date"
		)
		if last_sync_date:
			return formatdate(last_sync_date, "YYYY-MM-dd")
		else:
			current_fiscal_year = get_fiscal_year(nowdate(), as_dict=True)
			date = current_fiscal_year.year_start_date
			return formatdate(date, "YYYY-MM-dd")
