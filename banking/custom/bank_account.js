// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Account", {
	refresh(frm) {
		set_bank_fee_filter(frm);
	},

	account(frm) {
		set_bank_fee_filter(frm);
	},
});

function set_bank_fee_filter(frm) {
	if (!frm.doc.account) return;

	(async () => {
		const {
			message: { account_currency: currency },
		} = await frappe.db.get_value(
			"Account",
			frm.doc.account,
			"account_currency"
		);

		const {
			message: { company: company },
		} = await frappe.db.get_value(
			"Bank Account",
			frm.doc.bank_account,
			"company"
		);

		frm.set_query("bank_fee_account", () => ({
			filters: {
				account_type: "Cost of Goods Sold",
				account_currency: currency,
				company: company,
			},
		}));
	})();
}
