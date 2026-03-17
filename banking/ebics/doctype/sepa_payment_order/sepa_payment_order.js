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

		if (frm.doc.docstatus === 0 && frm.has_perm("write")) {
			frm.add_custom_button(__("Add Recipient"), () => {
				frm.trigger("add_recipient");
			});
			frm.add_custom_button(__("Update Amounts"), () => {
				frm.trigger("update_amounts");
			});
		}
	},

	add_recipient(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Add Recipient"),
			fields: [
				{
					fieldname: "recipient_doctype",
					label: __("DocType"),
					fieldtype: "Link",
					options: "DocType",
					reqd: 1,
					get_query: () => ({
						filters: { name: ["in", ["Supplier", "Employee"]] },
					}),
				},
				{
					fieldname: "recipient_name",
					label: __("Name"),
					fieldtype: "Dynamic Link",
					options: "recipient_doctype",
					reqd: 1,
					get_query: () => {
						const recipient_doctype = d.get_value("recipient_doctype");
						if (!recipient_doctype) {
							return;
						}
						if (recipient_doctype === "Supplier") {
							return {
								filters: {
									disabled: 0,
								},
							};
						} else if (recipient_doctype === "Employee") {
							return {
								filters: {
									status: ["in", ["Active", "Suspended"]],
								},
							};
						}
					},
				},
				{
					fieldname: "amount",
					label: __("Amount"),
					fieldtype: "Currency",
				},
			],
			primary_action_label: __("Add"),
			primary_action(values) {
				frappe.call({
					method:
						"banking.ebics.doctype.sepa_payment_order.sepa_payment_order.get_recipient_details",
					args: {
						doctype: values.recipient_doctype,
						name: values.recipient_name,
					},
					callback({ message }) {
						const new_row = {
							recipient: message.recipient,
							iban: message.iban,
							amount: values.amount,
						};
						//use last row if empty, otherwise add a new row
						if (
							frm.doc.payments?.length > 0 &&
							!frm.doc.payments.at(-1).recipient &&
							!frm.doc.payments.at(-1).iban
						) {
							Object.assign(frm.doc.payments.at(-1), new_row);
						} else {
							frm.add_child("payments", new_row);
						}
						frm.refresh_field("payments");
						d.hide();
					},
				});
			},
		});
		d.show();
	},

	async before_submit(frm) {
		await frappe
			.xcall(
				"banking.ebics.doctype.sepa_payment_order.sepa_payment_order.have_amounts_changed",
				{
					sepa_payment_order: frm.doc.name,
				}
			)
			.then((amounts_changed) => {
				if (!amounts_changed) {
					return;
				}

				return new Promise((resolve, reject) => {
					frappe.confirm(
						__(
							"Payment amounts have changed. Are you sure you want to submit without updating them first?"
						),
						() => resolve(),
						() => {
							frappe.validated = false;
							reject();
						}
					);
				});
			});
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

	update_amounts(frm) {
		frm
			.call("update_payment_amounts")
			.then((r) => {
				frappe.show_alert({
					message: __("Amounts updated."),
					indicator: "green",
				});
				frm.dirty();
			})
			.catch((e) => {
				frappe.show_alert({
					message: __("Amounts not updated."),
					indicator: "red",
				});
			});
	},
});

frappe.ui.form.on("SEPA Payment", {
	payments_add(frm) {
		frm.trigger("add_recipient");
	},
});
