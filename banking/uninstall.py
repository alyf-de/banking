import frappe


def before_uninstall():
	remove_custom_records()


def remove_custom_records():
	print("* removing custom records...")
	for record in frappe.get_hooks("alyf_banking_custom_records"):
		doctype = record.pop("doctype")
		frappe.db.delete(doctype, record)
