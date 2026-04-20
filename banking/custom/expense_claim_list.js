frappe.listview_settings["Expense Claim"] =
	frappe.listview_settings["Expense Claim"] || {};
const old_onload = frappe.listview_settings["Expense Claim"].onload;
const old_add_fields =
	frappe.listview_settings["Expense Claim"].add_fields || [];
frappe.listview_settings["Expense Claim"].add_fields = [
	...old_add_fields,
	"approval_status",
	"sepa_payment_order_status",
];

frappe.listview_settings["Expense Claim"].onload = function (listview) {
	if (old_onload) old_onload(listview);

	if (frappe.model.can_create("SEPA Payment Order")) {
		listview.page.add_action_item(__("SEPA Payment Order"), () => {
			const claims_to_pay = listview
				.get_checked_items()
				.filter(
					(item) =>
						item.status !== "Paid" &&
						item.docstatus === 1 &&
						item.approval_status === "Approved" &&
						!item.sepa_payment_order_status,
				)
				.map((item) => item.name);
			if (!claims_to_pay.length) {
				frappe.msgprint(
					__(
						"Only submitted, approved and unpaid Expense Claims without an existing SEPA Payment Order can be used. Rejected, paid or already linked claims were ignored.",
					),
					__("SEPA Payment Order"),
				);
				return;
			}
			frappe.call({
				type: "POST",
				method: "banking.custom.expense_claim.make_bulk_sepa_payment_order",
				args: {
					source_names: claims_to_pay,
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
