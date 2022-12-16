# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	custom_fields = {
		"Bank Account": [
			dict(
				owner="Administrator",
				fieldname="kosma_account_id",
				label="Kosma Account ID",
				fieldtype="Data",
				insert_after="mask",
				read_only=1,
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
			),
			dict(
				owner="Administrator",
				fieldname="consent_expiry",
				label="Consent Expiry",
				fieldtype="Datetime",
				insert_after="consent_id",
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

	create_custom_fields(custom_fields, update=True)
