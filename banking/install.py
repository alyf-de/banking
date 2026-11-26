import click
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from banking.custom_fields import get_custom_fields

INVOICE_REQUEST_EMAIL_TEMPLATE_NAME = "Bank Transaction Invoice Request"


def after_install():
	click.echo("Installing Banking Customizations ...")

	create_custom_fields(get_custom_fields())
	make_property_setters()
	insert_custom_records()
	create_invoice_request_email_template()


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


def create_invoice_request_email_template():
	subject = _("Invoice request for {{ name }}")
	response = _default_response()

	if frappe.db.exists("Email Template", INVOICE_REQUEST_EMAIL_TEMPLATE_NAME):
		template = frappe.get_doc("Email Template", INVOICE_REQUEST_EMAIL_TEMPLATE_NAME)
		template.subject = subject
		template.response = response
		template.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": INVOICE_REQUEST_EMAIL_TEMPLATE_NAME,
				"subject": subject,
				"response": response,
				"owner": frappe.session.user,
			}
		).insert(ignore_permissions=True)

	frappe.db.set_single_value(
		"Banking Settings",
		"invoice_request_email_template",
		INVOICE_REQUEST_EMAIL_TEMPLATE_NAME,
	)


def _default_response() -> str:
	return f"""<p>{_("Please provide the invoice for the following bank transaction.")}</p>

<p><strong>{_("Bank Transaction:")}</strong> {{{{ name }}}}<br>
<strong>{_("Date:")}</strong> {{{{ date }}}}<br>
{{% if deposit %}}<strong>{_("Deposit:")}</strong> {{{{ deposit }}}}<br>
{{% elif withdrawal %}}<strong>{_("Withdrawal:")}</strong> {{{{ withdrawal }}}}<br>
{{% endif %}}
{{% if description %}}<strong>{_("Description:")}</strong> {{{{ description | e }}}}<br>
{{% endif %}}
{{% if bank_party_name %}}<strong>{_("Party Name:")}</strong> {{{{ bank_party_name | e }}}}<br>
{{% endif %}}
{{% if party %}}<strong>{_("Party:")}</strong> {{{{ party_type | e }}}} — {{{{ party | e }}}}<br>
{{% endif %}}
{{% if reference_number %}}<strong>{_("Reference Number:")}</strong> {{{{ reference_number | e }}}}<br>
{{% endif %}}
{{% if bank_account %}}<strong>{_("Bank Account:")}</strong> {{{{ bank_account | e }}}}<br>
{{% endif %}}
</p>
"""
