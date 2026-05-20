// Copyright (c) 2026, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Transaction", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.trigger("set_included_fee_headline");
			frm.trigger("set_foreign_currency_included_fee_headline");
		}
	},

	set_included_fee_headline(frm) {
		if (!has_zero_amount_with_included_fee(frm)) {
			frm.dashboard.clear_headline();
			return;
		}

		frm.dashboard.set_headline(
			__(
				"This transaction has an <i>Included Fee</i> but no <i>Deposit</i> or <i>Withdrawal</i>. Automatic bank fee reconciliation was skipped; please review manually."
			),
			"orange"
		);
	},

	async set_foreign_currency_included_fee_headline(frm) {
		if (
			!has_deposit_with_included_fee(frm) ||
			!frm.doc.company ||
			!frm.doc.currency
		) {
			return;
		}

		const { message } = await frappe.db.get_value(
			"Company",
			frm.doc.company,
			"default_currency"
		);
		if (
			!message?.default_currency ||
			frm.doc.currency === message.default_currency
		) {
			return;
		}

		frm.dashboard.set_headline(
			__(
				"This transaction has an <i>Included Fee</i> in a foreign currency. Automatic reconciliation cannot consider that fee in Payment Entry deductions; reconcile and book the fee manually with a Journal Entry if appropriate."
			),
			"orange"
		);
	},
});

function has_deposit_with_included_fee(frm) {
	return (
		get_rounded_amount(frm, "deposit") > 0 &&
		get_rounded_amount(frm, "included_fee") > 0
	);
}

function has_zero_amount_with_included_fee(frm) {
	return (
		get_rounded_amount(frm, "deposit") === 0 &&
		get_rounded_amount(frm, "withdrawal") === 0 &&
		get_rounded_amount(frm, "included_fee") > 0
	);
}

function get_rounded_amount(frm, fieldname) {
	return flt(frm.doc[fieldname], precision(fieldname));
}
