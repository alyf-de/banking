import click
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from banking.custom_fields import get_custom_fields


def after_install():
	click.echo("Installing Banking Customizations ...")

	create_custom_fields(get_custom_fields())
	make_property_setters()
	insert_custom_records()


def after_app_install(app_name):
	if app_name == "banking":
		return

	print(f"Installing {app_name}-specific Banking customizations ...")

	app_custom_fields = {}
	for doctype, fields in get_custom_fields().items():
		module = frappe.db.get_value("DocType", doctype, "module")
		if module and frappe.db.get_value("Module Def", module, "app_name") == app_name:
			app_custom_fields[doctype] = fields

	if app_custom_fields:
		create_custom_fields(app_custom_fields)

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
		custom_record_copy = custom_record.copy()
		if required_apps := custom_record_copy.pop("_required_apps", None):
			installed_apps = frappe.get_installed_apps()
			if any(app not in installed_apps for app in required_apps):
				continue

		filters = custom_record_copy.copy()
		# Clean up filters. They need to be a plain dict without nested dicts or lists.
		for key, value in custom_record_copy.items():
			if isinstance(value, list | dict):
				del filters[key]

		if not frappe.db.exists(filters):
			frappe.get_doc(custom_record_copy).insert(ignore_if_duplicate=True)
