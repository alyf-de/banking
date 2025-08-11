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

	create_supplier_bank_account(frm) {
		const GERMAN_IBAN_PREFIX = "DE";
		const GERMAN_IBAN_LENGTH = 22;

		const dialog = frappe.prompt(
			[
				{
					fieldname: "iban",
					label: __("IBAN"),
					fieldtype: "Data",
					reqd: 1,
					onchange: () => {
						const iban = dialog.get_value("iban");

						if (
							iban?.trim().startsWith(GERMAN_IBAN_PREFIX) &&
							iban?.replaceAll(" ", "").length === GERMAN_IBAN_LENGTH
						) {
							dialog.set_df_property("bank", "hidden", true);
							dialog.set_df_property("bank", "reqd", false);
							dialog.set_value("bank", null);
						} else {
							dialog.set_df_property("bank", "hidden", false);
							dialog.set_df_property("bank", "reqd", true);
						}
					},
				},
				{
					fieldname: "bank",
					label: __("Bank"),
					fieldtype: "Link",
					options: "Bank",
				},
			],
			(values) => {
				frappe
					.xcall(
						"banking.custom.purchase_invoice.create_supplier_bank_account",
						{
							iban: values.iban,
							bank: values.bank,
							supplier: frm.doc.supplier,
							supplier_name: frm.doc.supplier_name,
						}
					)
					.then((bank_account) => {
						frm.set_value("supplier_bank_account", bank_account);
					});
			}
		);
	},
});
