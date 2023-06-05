import json
import requests

import frappe
from frappe import _


class ExceptionHandler():
	"""
	Log and throw error as received from Admin app.
	"""
	def __init__(self, exception):
		self.exception = exception
		self.handle_error()

	def handle_error(self):
		if not isinstance(self.exception, requests.exceptions.HTTPError):
			frappe.log_error(title=_("Banking Error"), message=frappe.get_traceback())
			raise

		response = self.exception.response
		self.handle_auth_error(response)
		self.handle_authorization_error(response)
		self.handle_txt_html_error(response)

		content = response.json().get("message", {})
		self.handle_frappe_server_error(content, response)
		self.handle_admin_error(content)

	def handle_auth_error(self, response):
		if not response.status_code == 401:
			return

		frappe.log_error(title=_("Banking Error"), message=response.content)
		frappe.throw(title=_("Banking Error"), msg=_("Authentication error due to invalid credentials."))

	def handle_authorization_error(self, response):
		if not response.status_code == 403:
			return

		frappe.log_error(title=_("Banking Error"), message=response.content)

		content = response.json().get("message", {})
		message = content if isinstance(content, str) else "Authorization error due to invalid access."
		frappe.throw(title=_("Banking Error"), msg=_(message))

	def handle_txt_html_error(self, response):
		"""
		Handle Gateway Error, etc. that dont have a JSON response.
		"""
		if "application/json" in response.headers.get("Content-Type", ""):
			return

		frappe.log_error(title=_("Banking Error"), message=response.content)
		frappe.throw(title=_("Banking Error"), msg=_("Something went wrong. Please retry in a while."))

	def handle_frappe_server_error(self, content, response):
		response_data = response.json()

		if not content and "exc_type" in response_data:
			frappe.log_error(title=_("Banking Error"), message=response.content)

			message = response_data.get("exception") or _("The server has errored. Please retry in some time.")
			frappe.throw(title=_("Banking Error"), msg=message)

	def handle_admin_error(self, content):
		frappe.log_error(title=_("Banking Error"), message=json.dumps(content))
		error_data = content.get("error", {}) or content.get("data", {})

		if error_data.get("errors"):
			error_list = [f"{err.get('location')} - {err.get('message')}" for err in error_data.get("errors")]
			message = _("Banking Action has failed due to the following error(s):")
			message += "<br><ul><li>" + "</li><li>".join(error_list) + "</li></ul>"

			frappe.throw(title=_("Banking Error"), msg=message)
		elif error_data.get("message"):
			frappe.throw(title=_("Banking Error"), msg=error_data.get("message"))


@frappe.whitelist()
def handle_ui_error(error: str, session_id_short: str):
	from banking.klarna_kosma_integration.admin import Admin

	error = json.loads(error)
	frappe.log_error(title=_("Banking Error"), message=error.get("message"))

	doc = frappe.get_doc("Klarna Kosma Session", session_id_short)
	session_id = doc.get_password("session_id")

	Admin().end_session(session_id, session_id_short)
