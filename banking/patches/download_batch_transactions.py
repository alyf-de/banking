import frappe


def execute():
	"""Enable _Download Batch Transactions_ checkbox for all EBICS Users that have _Split Batch Transactions_ enabled.

	This is required in order to keep the same behavior after introducing this new setting.
	"""
	for user in frappe.get_all("EBICS User", filters={"split_batch_transactions": 1}, pluck="name"):
		frappe.db.set_value("EBICS User", user, "download_batch_transactions", 1)
