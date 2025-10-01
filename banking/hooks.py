app_name = "banking"
app_title = "ALYF Banking"
app_publisher = "ALYF GmbH"
app_description = "Banking Integration by ALYF GmbH"
app_email = "hallo@alyf.de"
app_license = "GPLv3"
notification_email_logo = "/assets/banking/images/alyf-logo.png"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "bank_reconciliation_beta.bundle.css"
app_include_js = "/assets/banking/js/utils.js"

# include js, css files in header of web template
# web_include_css = "/assets/banking/css/banking.css"
# web_include_js = "/assets/banking/js/banking.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "banking/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Bank": "custom/bank.js",
	"Purchase Invoice": "custom/purchase_invoice.js",
	"Employee": "custom/employee.js",
	"Supplier": "custom/supplier.js",
}
doctype_list_js = {"Purchase Invoice": "custom/purchase_invoice_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "banking.utils.jinja_methods",
# 	"filters": "banking.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "banking.install.before_install"
after_install = "banking.install.after_install"

# Uninstallation
# ------------

before_uninstall = "banking.uninstall.before_uninstall"
# after_uninstall = "banking.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "banking.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {"Bank Transaction": "banking.overrides.bank_transaction.CustomBankTransaction"}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Bank Transaction": {
		"on_update_after_submit": "banking.overrides.bank_transaction.on_update_after_submit",
	},
	"Bank Account": {
		"before_validate": "banking.overrides.bank_account.before_validate",
	},
	"Employee": {
		"validate": "banking.custom.employee.validate",
	},
	"Purchase Invoice": {
		"sepa_payment_order_status_changed": "banking.custom.purchase_invoice.sepa_payment_order_status_changed",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"7 7-18 * * 1-5": [
			# At minute 7 past every hour from 7 through 18
			# on every day-of-week from Monday through Friday.
			"banking.klarna_kosma_integration.doctype.banking_settings.banking_settings.intraday_sync_ebics",
		],
		"42 4 * * *": [
			# Daily at 4:42 am
			"banking.klarna_kosma_integration.doctype.banking_settings.banking_settings.sync_all_accounts_and_transactions",
		],
	},
}

# Testing
# -------

before_tests = "banking.utils.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "banking.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "banking.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"banking.auth.validate"
# ]

export_python_type_annotations = True

alyf_banking_property_setters = {
	"Bank Account": [
		dict(
			fieldname="last_integration_date",
			property="read_only",
			value=1,
			property_type="Check",
		),
		dict(
			fieldname="last_integration_date",
			property="description",
			value="",
			property_type="Small Text",
		),
	]
}

# Bank Reconciliation Doctypes are defined in the respective apps.
# We only add "Bank Transaction" since thats not supported by ERPNext natively.
bank_reconciliation_doctypes = [
	"Bank Transaction",
]
get_matching_queries = "banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_matching_queries"
get_payment_entries = "banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.unpaid_vouchers.get_payment_entries"

alyf_banking_custom_records = [
	{
		"doctype": "DocType Link",
		"parent": "Purchase Invoice",
		"parentfield": "links",
		"parenttype": "Customize Form",
		"group": "Payment",
		"link_doctype": "SEPA Payment Order",
		"link_fieldname": "reference_name",
		"custom": 1,
	},
]
