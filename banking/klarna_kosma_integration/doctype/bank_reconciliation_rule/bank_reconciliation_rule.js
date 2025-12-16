// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Reconciliation Rule", {
	onload: function (frm) {
		render_bt_filters(frm);
	},
	refresh(frm) {
		set_target_account_filter(frm);
	},
	bank_account(frm) {
		set_target_account_filter(frm);
	},
});

let render_bt_filters = function (frm) {
	const parent = frm.fields_dict.filter_area.$wrapper;
	parent.empty();

	const filters =
		frm.doc.filters && frm.doc.filters !== "[]"
			? JSON.parse(frm.doc.filters)
			: [];

	frappe.model.with_doctype("Bank Transaction", () => {
		const filter_group = new frappe.ui.FilterGroup({
			parent: parent,
			doctype: "Bank Transaction",
			on_change: () => {
				frm.set_value("filters", JSON.stringify(filter_group.get_filters()));
			},
		});

		filter_group.add_filters_to_filter_group(filters);
	});
};

function set_target_account_filter(frm) {
	if (!frm.doc.bank_account) return;

	(async () => {
		const {
			message: { account },
		} = await frappe.db.get_value(
			"Bank Account",
			frm.doc.bank_account,
			"account"
		);

		const {
			message: { account_currency: currency },
		} = await frappe.db.get_value("Account", account, "account_currency");

		const {
			message: { company: company },
		} = await frappe.db.get_value(
			"Bank Account",
			frm.doc.bank_account,
			"company"
		);

		frm.set_query("target_account", () => ({
			filters: {
				account_currency: currency,
				company: company,
			},
		}));
	})();
}
