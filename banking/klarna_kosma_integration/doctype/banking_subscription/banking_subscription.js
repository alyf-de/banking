// Copyright (c) 2023, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Banking Subscription", {
  refresh: function (frm) {
	if (frm.doc.customer_id === undefined) {
		frm.call("ensure_customer_id").then(() => frm.reload_doc());
		return;
	}

    // set html content for the payment_plans field
	if (frm.doc.active_until === undefined || isInPast(frm.doc.active_until)) {
		frm.disable_save();
		frm.set_df_property(
			"payment_plans",
			"options",
			`<script async src="https://js.stripe.com/v3/pricing-table.js"></script>
			<stripe-pricing-table
				pricing-table-id="prctbl_1MqfFkIbzkQ8pB11g6ZoaYJG"
			publishable-key="pk_live_51IK5NZIbzkQ8pB114iOibhvfRKoiUIrfYxErx0tgHhcJgJ9044mRYM9rqd6tAqK9hJujRkmsBKH1qu8Xap1L1V3R00sNtv8SYa"
			client-reference-id="${frm.doc.customer_id}"
			></stripe-pricing-table>`
		);
	} else {
		frm.page.set_primary_action(__("Manage Subscription"), function () {
			window.open("https://billing.stripe.com/p/login/28o4hEaJP1GO9eE3cc", "_blank");
		});
		const active_msg = __(
			"Your subscription is active for up to {0} transactions per month until {1}.",
			[
				frm.doc.max_transactions,
				frappe.format(frm.doc.active_until, { fieldtype: "Date"})
			]
		);
		frm.set_df_property("payment_plans", "options", `<p>${ active_msg }</p>`);
	}
  }
});

function isInPast(isoDateString) {
	const inputDate = new Date(isoDateString);
	const currentDate = new Date();

	return inputDate < currentDate;
}
