# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from banking.klarna_kosma_integration.admin import Admin


class KlarnaKosmaSession(Document):
	"""DocType that stores Kosma Session details."""

	@frappe.whitelist()
	def end_kosma_session(self):
		session_id = self.get_password("session_id")
		Admin().end_session(session_id, self.session_id_short)
