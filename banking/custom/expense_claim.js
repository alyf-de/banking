frappe.ui.form.on("Expense Claim", {
	setup(frm) {
		frm.make_methods = frm.make_methods || {};
		frm.make_methods["SEPA Payment Order"] = () => {
			frm.trigger("make_sepa_payment_order");
		};
	},

	refresh(frm) {
		const has_outstanding =
			frm.doc.status !== "Paid" &&
			frm.doc.docstatus === 1 &&
			frm.doc.approval_status === "Approved" &&
			!frm.doc.sepa_payment_order_status &&
			flt(frm.doc.grand_total) - flt(frm.doc.total_amount_reimbursed) > 0;

		if (has_outstanding) {
			frm.add_custom_button(
				__("SEPA Payment Order"),
				() => frm.trigger("make_sepa_payment_order"),
<<<<<<< HEAD
				__("Create"),
=======
				__("Create")
>>>>>>> 938b226 (feat: create SEPA Payment Order from Expense Claim (#352))
			);
		}
	},

	make_sepa_payment_order(frm) {
		frappe.model.open_mapped_doc({
			method: "banking.custom.expense_claim.make_sepa_payment_order",
			frm: frm,
			freeze_message: __("Creating SEPA Payment Order ..."),
		});
	},
});
