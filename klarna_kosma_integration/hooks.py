from . import __version__ as app_version

app_name = "klarna_kosma_integration"
app_title = "Klarna Kosma Integration"
app_publisher = "ALYF GmbH"
app_description = "Klarna Kosma Open Banking Integration"
app_email = "hallo@alyf.de"
app_license = "MIT"
app_logo_url = "/assets/klarna_kosma_integration/images/alyf-logo.png"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/klarna_kosma_integration/css/klarna_kosma_integration.css"
# app_include_js = "/assets/klarna_kosma_integration/js/klarna_kosma_integration.js"

# include js, css files in header of web template
# web_include_css = "/assets/klarna_kosma_integration/css/klarna_kosma_integration.css"
# web_include_js = "/assets/klarna_kosma_integration/js/klarna_kosma_integration.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "klarna_kosma_integration/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
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
# 	"methods": "klarna_kosma_integration.utils.jinja_methods",
# 	"filters": "klarna_kosma_integration.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "klarna_kosma_integration.install.before_install"
after_install = "klarna_kosma_integration.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "klarna_kosma_integration.uninstall.before_uninstall"
# after_uninstall = "klarna_kosma_integration.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "klarna_kosma_integration.notifications.get_notification_config"

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

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"klarna_kosma_integration.klarna_kosma_integration.doctype.klarna_kosma_settings.klarna_kosma_settings.sync_all_accounts_and_transactions"
	],
}

# Testing
# -------

# before_tests = "klarna_kosma_integration.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "klarna_kosma_integration.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "klarna_kosma_integration.task.get_dashboard_data"
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
# 	"klarna_kosma_integration.auth.validate"
# ]

kosma_custom_fields = {
	"Bank Account": [
		dict(
			owner="Administrator",
			fieldname="kosma_account_id",
			label="Kosma Account ID",
			fieldtype="Data",
			insert_after="mask",
			read_only=1,
			translatable=0,
		)
	],
	"Bank Transaction": [
		dict(
			owner="Administrator",
			fieldname="kosma_party_name",
			label="Kosma Party Name",
			fieldtype="Data",
			insert_after="party",
			read_only=1,
			translatable=0,
		)
	],
	"Bank": [
		dict(
			owner="Administrator",
			fieldname="consent_section",
			label="Bank Consent Information",
			fieldtype="Section Break",
			insert_after="bank_transaction_mapping",
		),
		dict(
			owner="Administrator",
			fieldname="consent_id",
			label="Consent ID",
			fieldtype="Data",
			insert_after="consent_section",
			read_only=1,
			translatable=0,
		),
		dict(
			owner="Administrator",
			fieldname="consent_start",
			label="Consent Start Date",
			fieldtype="Date",
			insert_after="consent_id",
			read_only=1,
		),
		dict(
			owner="Administrator",
			fieldname="consent_expiry",
			label="Consent Expiry Date",
			fieldtype="Datetime",
			insert_after="consent_start",
			read_only=1,
		),
		dict(
			owner="Administrator",
			fieldname="consent_cb",
			fieldtype="Column Break",
			insert_after="consent_expiry",
		),
		dict(
			owner="Administrator",
			fieldname="consent_token",
			label="Consent Token",
			fieldtype="Password",
			length=2760,
			insert_after="consent_cb",
			read_only=1,
		),
	],
}

kosma_property_setters = {
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
