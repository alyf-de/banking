# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

<<<<<<< HEAD
# import frappe
=======
import json

import frappe
from frappe import _
>>>>>>> 29351ff (feat: re-import ebics request (#320))
from frappe.model.document import Document

from banking.ebics.utils import import_ebics_json, register_fintech


class EBICSRequest(Document):
<<<<<<< HEAD
	pass
=======
	@frappe.whitelist()
	def re_import(self):
		"""Re-import the EBICS transactions from the response."""
		ebics_user = frappe.get_doc("EBICS User", self.ebics_user)
		try:
			data = json.loads(self.response)
		except (json.JSONDecodeError, TypeError):
			frappe.throw(_("Invalid data for re-import."))

		if not isinstance(data, dict):
			frappe.throw(_("Invalid data for re-import."))

		register_fintech(needs_license_key=True)
		import_ebics_json(ebics_user, data)


def sanitize_filename(filename: str) -> str:
	"""
	Sanitize a filename for use in zip files by removing path components.

	Args:
		filename: The original filename from user input

	Returns:
		A sanitized filename that's safe to use
	"""
	from os.path import basename

	if not filename or not isinstance(filename, str):
		return "unnamed_file"

	# Remove any path components to get just the basename
	filename = basename(filename).strip()

	# Fallback if filename becomes empty after sanitization
	return filename or "unnamed_file"


@frappe.whitelist()
def download_files(name: str):
	"""
	Download the files from the EBICS Request as a zip file.

	Args:
		name: The name of the EBICS Request.
	"""
	import json
	import zipfile
	from io import BytesIO

	from frappe import _

	doc: EBICSRequest = frappe.get_doc("EBICS Request", name)
	doc.check_permission()

	try:
		data = json.loads(doc.response)
	except (json.JSONDecodeError, TypeError):
		frappe.throw(_("No data available for download."))

	if not isinstance(data, dict):
		frappe.throw(_("Invalid data available for download."))

	zip_buffer = BytesIO()

	with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
		for file_name, file_data in data.items():
			safe_filename = sanitize_filename(file_name)
			zip_file.writestr(safe_filename, file_data)

	frappe.response["filecontent"] = zip_buffer.getvalue()
	frappe.response["filename"] = f"{name}.zip"
	frappe.response["type"] = "binary"
>>>>>>> 29351ff (feat: re-import ebics request (#320))
