from frappe import get_hooks
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(get_hooks("alyf_banking_custom_fields"))
