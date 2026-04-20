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

		frm.set_query("employee_bank_account", (doc) => {
			return {
				filters: {
					party_type: "Employee",
					party: doc.business_trip_employee,
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
				__("Create"),
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

	create_supplier_bank_account(frm) {
		banking.utils
			.create_party_bank_account(
				"Supplier",
				frm.doc.supplier,
				frm.doc.supplier_name,
			)
			.then((bank_account) => {
				frm.set_value("supplier_bank_account", bank_account);
				frappe.show_alert({
					message: __("Supplier Bank Account was created."),
					indicator: "green",
				});
			})
			.catch(() => {
				frappe.show_alert({
					message: __("Supplier Bank Account was not created."),
					indicator: "yellow",
				});
			});
	},

	create_employee_bank_account(frm) {
		banking.utils
			.create_party_bank_account("Employee", frm.doc.business_trip_employee)
			.then((bank_account) => {
				frm.set_value("employee_bank_account", bank_account);
				frappe.show_alert({
					message: __("Employee Bank Account was created."),
					indicator: "green",
				});
			})
			.catch(() => {
				frappe.show_alert({
					message: __("Employee Bank Account was not created."),
					indicator: "yellow",
				});
			});
	},
});
