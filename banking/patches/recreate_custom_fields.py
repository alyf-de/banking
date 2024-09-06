from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe import get_hooks


def execute():
	create_custom_fields(get_hooks("kosma_custom_fields"))
