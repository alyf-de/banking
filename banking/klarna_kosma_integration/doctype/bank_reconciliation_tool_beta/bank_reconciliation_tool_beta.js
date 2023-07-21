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
			if (!frm.doc.bank_account) {
				frappe.throw(
					{
						message: __("Please set the 'Bank Account' filter"),
						indicator: "red",
						title: __("Filter Required")
					}
				);
			}

			frm.remove_custom_button(__("Upload a Bank Statement"));
			frm.add_custom_button(
				__("Upload a Bank Statement"),
				() => frm.events.route_to_bank_statement_import(frm),
			);

			frm.events.build_reconciliation_area(frm);
		});
		frm.change_custom_button_type("Get Bank Transactions", null, "primary");

		frm.$reconciliation_area = frm.get_field("reconciliation_action_area").$wrapper;
		frm.events.setup_empty_state(frm);
	},

	setup_empty_state: function(frm) {
		frm.$reconciliation_area.empty();
		let empty_area = frm.$reconciliation_area.append(`
			<div class="bank-reco-beta-empty-state">
				<p>
					${__("Set Filters and Get Bank Transactions")}
				</p>
				<p>${__("Or")}</p>
			</div>
		`).find(".bank-reco-beta-empty-state");

		frappe.utils.add_custom_button(
			__("Upload a Bank Statement"),
			() => frm.events.route_to_bank_statement_import(frm),
			"",
			__("Upload a Bank Statement"),
			"btn-primary",
			$(empty_area),
		)
	},

	route_to_bank_statement_import(frm) {
		frappe.call({
			method:
				"erpnext.accounts.doctype.bank_statement_import.bank_statement_import.upload_bank_statement",
			args: {
				dt: frm.doc.doctype,
				dn: frm.doc.name,
				company: frm.doc.company,
				bank_account: frm.doc.bank_account,
			},
			callback: function (r) {
				if (!r.exc) {
					var doc = frappe.model.sync(r.message);
					frappe.set_route("Form", doc[0].doctype, doc[0].name);
				}
			},
		})
	},

	bank_account: function (frm) {
		frappe.db.get_value(
			"Bank Account",
			frm.doc.bank_account,
			"account",
			(r) => {
				frappe.db.get_value(
					"Account",
					r.account,
					"account_currency",
					(r) => {
						frm.doc.account_currency = r.account_currency;
						frm.trigger("bank_statement_from_date");
						frm.trigger("bank_statement_to_date");
						frm.trigger("render_summary");
					}
				);
			}
		);

	},

	bank_statement_from_date: function (frm) {
		frm.trigger("get_account_opening_balance");
	},

	bank_statement_to_date: function (frm) {
		frm.trigger("get_account_closing_balance");
		frm.trigger("render_summary");
	},

	bank_statement_closing_balance: function (frm) {
		frm.trigger("render_summary");
	},

	get_account_opening_balance(frm) {
		if (frm.doc.bank_account && frm.doc.bank_statement_from_date) {
			frappe.call({
				method:
					"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_account_balance",
				args: {
					bank_account: frm.doc.bank_account,
					till_date: frm.doc.bank_statement_from_date,
				},
				callback: (response) => {
					frm.set_value("account_opening_balance", response.message);
				},
			});
		}
	},

	get_account_closing_balance(frm) {
		if (frm.doc.bank_account && frm.doc.bank_statement_to_date) {
			return frappe.call({
				method:
					"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_account_balance",
				args: {
					bank_account: frm.doc.bank_account,
					till_date: frm.doc.bank_statement_to_date,
				},
				callback: (response) => {
					frm.cleared_balance = response.message;
				},
			});
		}
	},

	render_summary: function(frm) {
		frm.get_field("reconciliation_tool_cards").$wrapper.empty();

		frappe.require("bank_reconciliation_beta.bundle.js", () => {
			let difference = flt(frm.doc.bank_statement_closing_balance) - flt(frm.cleared_balance);
			let difference_color = difference >= 0 ?  "text-success" : "text-danger";

			frm.summary_card = new erpnext.accounts.bank_reconciliation.SummaryCard({
				$wrapper: frm.get_field("reconciliation_tool_cards").$wrapper,
				values: {
					"Bank Closing Balance": [frm.doc.bank_statement_closing_balance],
					"ERP Closing Balance": [frm.cleared_balance],
					"Difference": [difference, difference_color]
				},
				currency: frm.doc.account_currency,
			})
		});
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
