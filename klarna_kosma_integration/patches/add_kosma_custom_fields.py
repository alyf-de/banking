# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Bank Account",
		dict(
			owner="Administrator",
			fieldname="kosma_account_id",
			label="Kosma Account ID",
			fieldtype="Data",
			insert_after="mask",
			read_only=1,
		),
	)
