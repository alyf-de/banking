# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from klarna_kosma_integration.klarna_kosma_integration.kosma import Kosma


class KlarnaKosmaSession(Document):
	"""DocType that stores Kosma Session details."""

	@frappe.whitelist()
	def end_kosma_session(self):
		session_id = self.get_password("session_id")
		kosma = Kosma()
		kosma.end_session(kosma.get_flow(), session_id, self.session_id_short)
