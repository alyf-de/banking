import click
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def after_install():
	click.echo("Installing Banking Customizations ...")

	create_custom_fields(frappe.get_hooks("alyf_banking_custom_fields"))
	make_property_setters()
	insert_custom_records()


def make_property_setters():
	for doctypes, property_setters in frappe.get_hooks("alyf_banking_property_setters", {}).items():
		if isinstance(doctypes, str):
			doctypes = (doctypes,)

		for doctype in doctypes:
			for property_setter in property_setters:
				make_property_setter(
					doctype,
					**property_setter,
					validate_fields_for_doctype=False,
					for_doctype=not property_setter.get("fieldname"),
				)


def insert_custom_records():
	for custom_record in frappe.get_hooks("alyf_banking_custom_records"):
		filters = custom_record.copy()
		# Clean up filters. They need to be a plain dict without nested dicts or lists.
		for key, value in custom_record.items():
			if isinstance(value, list | dict):
				del filters[key]

		if not frappe.db.exists(filters):
			frappe.get_doc(custom_record).insert(ignore_if_duplicate=True)
