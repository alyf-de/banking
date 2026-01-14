// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Account", {
	refresh(frm) {
		frm.trigger("set_fee_account_query");
	},

	account(frm) {
		frm.trigger("set_fee_account_query");
	},

	async set_fee_account_query(frm) {
		if (!frm.doc.account) {
			return;
		}

		const {
			message: { account_currency: currency, company: company },
		} = await frappe.db.get_value("Account", frm.doc.account, [
			"account_currency",
			"company",
		]);

		frm.set_query("bank_fee_account", (doc) => {
			return {
				filters: {
					root_type: "Expense",
					account_currency: currency,
					company: company,
				},
			};
		});
	},
});
