// Copyright (c) 2026, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Transaction", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.trigger("set_included_fee_headline");
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
});

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
