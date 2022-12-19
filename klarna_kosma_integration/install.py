import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	create_custom_fields(frappe.get_hooks("kosma_custom_fields"))
