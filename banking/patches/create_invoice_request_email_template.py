import frappe

from banking.install import create_invoice_request_email_template


def execute():
	frappe.reload_doc("email", "doctype", "email_template")
	create_invoice_request_email_template()
