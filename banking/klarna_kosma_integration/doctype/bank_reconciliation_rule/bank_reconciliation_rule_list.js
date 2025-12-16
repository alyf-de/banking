// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.listview_settings["Bank Reconciliation Rule"] = {
	add_fields: ["docstatus", "disabled"],
	has_indicator_for_draft: true,

	get_indicator: function (doc) {
		// Submitted documents
		if (doc.docstatus === 1) {
			if (doc.disabled === 1) {
				return [__("Disabled"), "orange", "disabled,=,1"];
			} else {
				return [__("Active"), "green", "docstatus,=,1"];
			}
		}

		// Draft documents
		if (doc.docstatus === 0) {
			return [__("Draft"), "blue", "docstatus,=,0"];
		}
	},
};
