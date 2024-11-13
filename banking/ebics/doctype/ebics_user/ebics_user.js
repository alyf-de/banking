// Copyright (c) 2024, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("EBICS User", {
	refresh(frm) {
		if (frm.doc.initialized && !frm.doc.bank_keys_activated) {
			frm.dashboard.set_headline(
				__("Please print the attached INI letter, send it to your bank and wait for confirmation. Then verify the bank keys.")
			);
		}

		if (!frm.doc.initialized || frappe.boot.developer_mode) {
			frm.add_custom_button(
				__("Initialize"),
				() => {
					frappe.prompt(
						[
							{
								fieldname: "passphrase",
								label: __("Passphrase"),
								fieldtype: "Password",
								description: __("Set a new password for downloading bank statements from your bank.")
							},
							{
								fieldname: "store_passphrase",
								label: __("Store Passphrase"),
								fieldtype: "Check",
								default: 1,
								description: __("Store the passphrase in the ERPNext database to enable automated, regular download of bank statements.")
							},
							{
								fieldname: "signature_passphrase",
								label: __("Signature Passphrase"),
								fieldtype: "Password",
								description: __("Set a new password for uploading transactions to your bank.")
							},
							{
								fieldname: "info",
								fieldtype: "HTML",
								options: __(
									"Note: When you lose these passwords, you will have to go through the initialization process with your bank again."
								)
							}
						],
						(values) => {
							frappe.call({
								method: "banking.ebics.doctype.ebics_user.ebics_user.initialize",
								args: { ebics_user: frm.doc.name, ...values },
								freeze: true,
								freeze_message: __("Initializing..."),
								callback: () => frm.reload_doc(),
							});
						},
						__("Initialize EBICS User")
					);
				},
				frm.doc.initialized ? __("Actions") : null
			);
		}

		if (frm.doc.initialized && (!frm.doc.bank_keys_activated || frappe.boot.developer_mode)) {
			frm.add_custom_button(
				__("Verify Bank Keys"),
				async () => {
					bank_keys = await get_bank_keys(frm.doc.name);
					if (!bank_keys) {
						return;
					}

					message = __(
						"Please confirm that the following keys are identical to the ones mentioned on your bank's letter:"
					);
					frappe.confirm(
						`<p>${message}</p>
						<pre>${bank_keys}</pre>`,
						async () => {
							await confirm_bank_keys(frm.doc.name);
							frm.reload_doc();
						}
					);
				},
				frm.doc.bank_keys_activated ? __("Actions") : null
			);
		}

		if (frm.doc.initialized && frm.doc.bank_keys_activated) {
			frm.add_custom_button(__("Download Bank Statements"), () => {
				download_bank_statements(frm.doc.name, !frm.doc.passphrase);
			});
		}
	},
});

async function get_bank_keys(ebics_user) {
	try {
		return await frappe.xcall(
			"banking.ebics.doctype.ebics_user.ebics_user.download_bank_keys",
			{ ebics_user: ebics_user }
		);
	} catch (e) {
		frappe.show_alert({
			message: e || __("An error occurred"),
			indicator: "red",
		});
	}
}

async function confirm_bank_keys(ebics_user) {
	try {
		await frappe.xcall(
			"banking.ebics.doctype.ebics_user.ebics_user.confirm_bank_keys",
			{ ebics_user: ebics_user }
		);
		frappe.show_alert({
			message: __("Bank keys confirmed"),
			indicator: "green",
		});
	} catch (e) {
		frappe.show_alert({
			message: e || __("An error occurred"),
			indicator: "red",
		});
	}
}

function download_bank_statements(ebics_user, needs_passphrase) {
	const fields = [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.now_date(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.now_date(),
		},
	];

	if (needs_passphrase) {
		fields.push({
			fieldname: "passphrase",
			label: __("Passphrase"),
			fieldtype: "Password",
			reqd: true
		});
	}

	frappe.prompt(
		fields,
		async (values) => {
			try {
				await frappe.xcall(
					"banking.ebics.doctype.ebics_user.ebics_user.download_bank_statements",
					{
						ebics_user: ebics_user,
						from_date: values.from_date,
						to_date: values.to_date,
						passphrase: values.passphrase,
					}
				);
				frappe.show_alert({
					message: __("Bank statements are being downloaded in the background."),
					indicator: "blue",
				});
			} catch (e) {
				frappe.show_alert({
					message: e || __("An error occurred"),
					indicator: "red",
				});
			}
		},
		__("Download Bank Statements")
	);
}
