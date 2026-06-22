import frappe

from banking.custom_fields import get_custom_fields


def before_uninstall():
	remove_custom_records()
	remove_custom_fields()
	remove_property_setters()


def before_app_uninstall(app_name):
	if app_name == "banking":
		return

	print(f"* removing {app_name}-specific Banking customizations...")
	remove_app_custom_fields(app_name)
	remove_app_custom_records(app_name)


def remove_app_custom_fields(app_name):
	print(f"* removing {app_name} custom fields...")
	from frappe.custom.doctype.custom_field.custom_field import delete_custom_fields

	from banking.custom_fields import get_custom_fields

	app_custom_fields = {}
	for doctype, fields in get_custom_fields().items():
		module = frappe.db.get_value("DocType", doctype, "module")
		if module and frappe.db.get_value("Module Def", module, "app_name") == app_name:
			app_custom_fields[doctype] = fields

	if app_custom_fields:
		delete_custom_fields(app_custom_fields)


def remove_app_custom_records(app_name):
	print(f"* removing {app_name} custom records...")
	doctypes_to_clear = set()
	for record in frappe.get_hooks("alyf_banking_custom_records"):
		record_copy = record.copy()
		required_apps = record_copy.pop("_required_apps", None)
		if required_apps and app_name in required_apps:
			doctype = record_copy.pop("doctype")

			filters = record_copy.copy()
			# Clean up filters. They need to be a plain dict without nested dicts or lists.
			for key, value in record_copy.items():
				if isinstance(value, list | dict):
					del filters[key]

			frappe.db.delete(doctype, filters)
			if parent := filters.get("parent"):
				doctypes_to_clear.add(parent)

	for parent in doctypes_to_clear:
		frappe.clear_cache(doctype=parent)


def remove_custom_records():
	print("* removing custom records...")
	doctypes_to_clear = set()
	for record in frappe.get_hooks("alyf_banking_custom_records"):
		record_copy = record.copy()
		record_copy.pop("_required_apps", None)
		doctype = record_copy.pop("doctype")

		filters = record_copy.copy()
		# Clean up filters. They need to be a plain dict without nested dicts or lists.
		for key, value in record_copy.items():
			if isinstance(value, list | dict):
				del filters[key]

		frappe.db.delete(doctype, filters)
		if parent := filters.get("parent"):
			doctypes_to_clear.add(parent)

	for parent in doctypes_to_clear:
		frappe.clear_cache(doctype=parent)


def remove_custom_fields():
	print("* removing custom fields...")
	from frappe.custom.doctype.custom_field.custom_field import delete_custom_fields

	custom_fields_to_delete = {}
	for doctypes, custom_fields in get_custom_fields().items():
		if isinstance(doctypes, str):
			doctypes = (doctypes,)

		for doctype in doctypes:
			custom_fields_to_delete[doctype] = custom_fields

	delete_custom_fields(custom_fields_to_delete)


def remove_property_setters():
	print("* removing property setters...")
	from frappe.custom.doctype.property_setter.property_setter import delete_property_setter

	for doctypes, property_setters in frappe.get_hooks("alyf_banking_property_setters", {}).items():
		if isinstance(doctypes, str):
			doctypes = (doctypes,)

		for doctype in doctypes:
			for property_setter in property_setters:
				delete_property_setter(
					doctype,
					property=property_setter.get("property"),
					field_name=property_setter.get("fieldname"),
				)
