// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Reconciliation Rule", {
	onload: function (frm) {
		frm.trigger("render_bt_filters");
	},
	refresh(frm) {
		frm.trigger("set_target_account_query");
	},
	bank_account(frm) {
		frm.trigger("set_target_account_query");
	},
	async set_target_account_query(frm) {
		if (!frm.doc.bank_account) {
			return;
		}

		const {
			message: { account },
		} = await frappe.db.get_value(
			"Bank Account",
			frm.doc.bank_account,
			"account"
		);

		const {
			message: { account_currency: currency, company: company },
		} = await frappe.db.get_value("Account", account, [
			"account_currency",
			"company",
		]);

		frm.set_query("target_account", () => ({
			filters: {
				account_currency: currency,
				company: company,
			},
		}));
	},
	render_bt_filters(frm) {
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
	},
});
