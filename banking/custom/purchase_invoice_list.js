const old_onload = frappe.listview_settings["Purchase Invoice"].onload;

frappe.listview_settings["Purchase Invoice"].onload = function (listview) {
	old_onload(listview);

	if (frappe.model.can_create("SEPA Payment Order")) {
		listview.page.add_action_item(__("SEPA Payment Order"), () => {
			const invoices_to_pay = listview
				.get_checked_items()
				.filter((item) => item.status !== "Paid" && item.docstatus === 1)
				.map((item) => item.name);
			frappe.call({
				type: "POST",
				method: "banking.custom.purchase_invoice.make_bulk_sepa_payment_order",
				args: {
					source_names: invoices_to_pay,
				},
				freeze: true,
				freeze_message: __("Creating SEPA Payment Order ..."),
				callback: function (r) {
					if (!r.exc && r.message) {
						frappe.model.sync(r.message);
						frappe.get_doc(
							r.message.doctype,
							r.message.name,
						).__run_link_triggers = true;
						frappe.set_route("Form", r.message.doctype, r.message.name);
					}
				},
			});
		});
	}
};
