// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.listview_settings["Bank Reconciliation Rule"] = {
	add_fields: ["docstatus", "disabled", "priority"],
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

	onload: function (listview) {
		if (!frappe.model.can_write("Bank Reconciliation Rule")) {
			return;
		}
		listview.page.add_inner_button(__("Reorder by Priority"), () => {
			frappe.require(
				[
					"bank_reconciliation_rule_reorder.bundle.js",
					"bank_reconciliation_rule_reorder.bundle.css",
				],
				() => banking.bank_reconciliation.open_reorder_dialog(listview)
			);
		});
	},
};
