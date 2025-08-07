frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.status !== "Paid" && frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("SEPA Payment Order"),
				() => {
					frappe.model.open_mapped_doc({
						method: "banking.custom.purchase_invoice.make_sepa_payment_order",
						frm: frm,
						freeze_message: __("Creating SEPA Payment Order ..."),
					});
				},
				__("Create")
			);
		}
	},
});
