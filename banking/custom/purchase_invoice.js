frappe.ui.form.on("Purchase Invoice", {
	setup(frm) {
		frm.make_methods = frm.make_methods || {};
		frm.make_methods["SEPA Payment Order"] = () => {
			frm.trigger("make_sepa_payment_order");
		};

		frm.set_query("supplier_bank_account", (doc) => {
			return {
				filters: {
					party_type: "Supplier",
					party: doc.supplier,
				},
			};
		});
	},

	refresh(frm) {
		const has_unpaid_payments = () =>
			frm.doc.payment_schedule.filter((x) => !x.sepa_payment_order_status)
				.length > 0;

		if (
			frm.doc.status !== "Paid" &&
			frm.doc.docstatus === 1 &&
			has_unpaid_payments()
		) {
			frm.add_custom_button(
				__("SEPA Payment Order"),
				() => frm.trigger("make_sepa_payment_order"),
				__("Create")
			);
		}
	},

	make_sepa_payment_order(frm) {
		frappe.model.open_mapped_doc({
			method: "banking.custom.purchase_invoice.make_sepa_payment_order",
			frm: frm,
			freeze_message: __("Creating SEPA Payment Order ..."),
		});
	},
});
