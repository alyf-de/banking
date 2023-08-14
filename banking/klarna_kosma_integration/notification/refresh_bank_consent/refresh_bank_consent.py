import frappe


def get_context(context):
	app_logo_url = frappe.get_hooks("notification_email_logo")[-1]
	context["app_logo_url"] = frappe.utils.get_url(app_logo_url)
