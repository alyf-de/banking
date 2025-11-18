import frappe

from banking.custom_fields import get_custom_fields


def before_uninstall():
	remove_custom_records()
	remove_custom_fields()
	remove_property_setters()


def remove_custom_records():
	print("* removing custom records...")
	for record in frappe.get_hooks("alyf_banking_custom_records"):
		doctype = record.pop("doctype")
		frappe.db.delete(doctype, record)


def remove_custom_fields():
	print("* removing custom fields...")
	for doctypes, custom_fields in get_custom_fields().items():
		if isinstance(doctypes, str):
			doctypes = (doctypes,)

		for doctype in doctypes:
			for cf in custom_fields:
				frappe.db.delete(
					"Custom Field",
					{
						"dt": doctype,
						"fieldname": cf.get("fieldname"),
					},
				)


def remove_property_setters():
	print("* removing property setters...")
	for doctypes, property_setters in frappe.get_hooks("alyf_banking_property_setters", {}).items():
		if isinstance(doctypes, str):
			doctypes = (doctypes,)

		for doctype in doctypes:
			for property_setter in property_setters:
				frappe.db.delete(
					"Property Setter",
					{
						"doc_type": doctype,
						"field_name": property_setter.get("fieldname"),
						"property": property_setter.get("property"),
						"value": property_setter.get("value"),
					},
				)
