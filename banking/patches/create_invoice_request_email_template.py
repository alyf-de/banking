import frappe
from frappe import _

INVOICE_REQUEST_EMAIL_TEMPLATE_NAME = "Bank Transaction Invoice Request"


def execute():
	frappe.reload_doc("email", "doctype", "email_template")

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
{{% if description %}}<strong>{_("Description:")}</strong> {{{{ description }}}}<br>
{{% endif %}}
{{% if bank_party_name %}}<strong>{_("Party Name:")}</strong> {{{{ bank_party_name }}}}<br>
{{% endif %}}
{{% if party %}}<strong>{_("Party:")}</strong> {{{{ party_type }}}} — {{{{ party }}}}<br>
{{% endif %}}
{{% if reference_number %}}<strong>{_("Reference Number:")}</strong> {{{{ reference_number }}}}<br>
{{% endif %}}
{{% if bank_account %}}<strong>{_("Bank Account:")}</strong> {{{{ bank_account }}}}<br>
{{% endif %}}
</p>
"""
