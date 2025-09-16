// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("SEPA Payment Order", {
	setup(frm) {
		frm.set_query("bank_account", function (doc) {
			return {
				filters: {
					company: doc.company,
					is_company_account: 1,
				},
			};
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.has_perm("submit")) {
			frm.add_custom_button(
				__("Download as XML"),
				() => {
					frm.trigger("download_xml_file");
				},
				__("Actions")
			);
			// frm.add_custom_button(
			// 	__("Send to Bank"),
			// 	() => {
			// 		frm.trigger("send_to_bank");
			// 	},
			// 	__("Actions")
			// );
		}
	},

	download_xml_file(frm) {
		open_url_post(
			"/api/method/banking.ebics.doctype.sepa_payment_order.sepa_payment_order.download_xml_file",
			{
				sepa_payment_order: frm.doc.name,
			}
		);
	},

	send_to_bank(frm) {
		const dialog = frappe.prompt(
			[
				{
					fieldname: "ebics_user",
					label: __("EBICS User"),
					fieldtype: "Link",
					options: "EBICS User",
					reqd: 1,
					get_query: () => {
						return {
							filters: {
								company: frm.doc.company,
								bank: frm.doc.bank,
								initialized: 1,
								bank_keys_activated: 1,
							},
						};
					},
					/**
					 * If the passphrase is stored in the EBICS User, hide the
					 * passphrase field and set it to not required.
					 */
					onchange: () => {
						const ebics_user = dialog.get_value("ebics_user");
						if (!ebics_user) {
							dialog.set_df_property("passphrase", "reqd", 1);
							dialog.set_df_property("passphrase", "hidden", 0);
							return;
						}

						frappe.db.get_value("EBICS User", ebics_user, "passphrase", (r) => {
							if (r.passphrase) {
								dialog.set_df_property("passphrase", "reqd", 0);
								dialog.set_df_property("passphrase", "hidden", 1);
							} else {
								dialog.set_df_property("passphrase", "reqd", 1);
								dialog.set_df_property("passphrase", "hidden", 0);
							}
						});
					},
				},
				{
					fieldname: "sig_passphrase",
					label: __("Signature Passphrase"),
					fieldtype: "Password",
					placeholder: __("Enter your signature passphrase"),
					reqd: 1,
				},
				{
					fieldname: "passphrase",
					label: __("Passphrase"),
					fieldtype: "Password",
					placeholder: __("Enter your passphrase"),
					reqd: 0,
				},
			],
			(values) => {
				frappe
					.xcall(
						"banking.ebics.doctype.sepa_payment_order.sepa_payment_order.send_to_bank",
						{
							sepa_payment_order: frm.doc.name,
							ebics_user_id: values.ebics_user,
							sig_passphrase: values.sig_passphrase,
							passphrase: values.passphrase,
						}
					)
					.then((r) => {
						frappe.show_alert({
							message: __("Payment Order has been sent to bank."),
							indicator: "green",
						});
					})
					.catch(() => {
						frappe.show_alert({
							message: __("Payment Order has not been sent to bank."),
							indicator: "red",
						});
					});
			}
		);
	},
});
