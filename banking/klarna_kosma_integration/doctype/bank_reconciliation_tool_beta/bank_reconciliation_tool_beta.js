// Copyright (c) 2023, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bank Reconciliation Tool Beta', {
	setup: function (frm) {
		frm.set_query("bank_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					'is_company_account': 1
				},
			};
		});
	},

	onload: function (frm) {
		// Set default filter dates
		let today = frappe.datetime.get_today()
		frm.doc.bank_statement_from_date = frappe.datetime.add_months(today, -1);
		frm.doc.bank_statement_to_date = today;
	},

	refresh: function(frm) {
		frm.disable_save();
		frm.fields_dict["filters_section"].collapse(false);

		frm.add_custom_button(__("Get Bank Transactions"), function() {
			frm.events.build_reconciliation_area(frm);
		});
		frm.change_custom_button_type("Get Bank Transactions", null, "primary");

		frm.$reconciliation_area = frm.get_field("reconciliation_action_area").$wrapper;
		frm.events.setup_empty_state(frm);
	},

	setup_empty_state: function(frm) {
		frm.$reconciliation_area.empty();
		let empty_area = frm.$reconciliation_area.append(`
			<div class="empty-state">
				<p>${__("Set the right filters to fetch some Bank Transactions")}</p>
				<p>${__("Or")}</p>
			</div>
		`).find(".empty-state");

		frappe.utils.add_custom_button(
			__("Upload a Bank Statement"),
			() => this.route_to_bank_statement_import(),
			"",
			__("Upload a Bank Statement"),
			"btn-default",
			$(empty_area),
		)
	},

	route_to_bank_statement_import() {
		frappe.call({
			method:
				"erpnext.accounts.doctype.bank_statement_import.bank_statement_import.upload_bank_statement",
			args: {
				dt: this.doc.doctype,
				dn: this.doc.name,
				company: this.doc.company,
				bank_account: this.doc.bank_account,
			},
			callback: function (r) {
				if (!r.exc) {
					var doc = frappe.model.sync(r.message);
					frappe.set_route("Form", doc[0].doctype, doc[0].name);
				}
			},
		})
	},

	build_reconciliation_area: function(frm) {
		frappe.require("bank_reconciliation_beta.bundle.js", () =>
			frm.panel_manager = new erpnext.accounts.bank_reconciliation.PanelManager({
				doc: frm.doc,
				$wrapper: frm.$reconciliation_area,
			})
		);
	},
});
