# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EBICSRequest(Document):
	pass


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
	except json.JSONDecodeError:
		frappe.throw(_("No data available for download."))

	if not isinstance(data, dict):
		frappe.throw(_("Invalid data available for download."))

	zip_buffer = BytesIO()

	with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
		for file_name, file_data in data.items():
			zip_file.writestr(file_name, file_data)

	frappe.response["filecontent"] = zip_buffer.getvalue()
	frappe.response["filename"] = f"{name}.zip"
	frappe.response["type"] = "binary"
