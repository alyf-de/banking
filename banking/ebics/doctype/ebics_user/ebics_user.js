// Copyright (c) 2024, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("EBICS User", {
	refresh(frm) {
		if (frm.doc.initialized && !frm.doc.bank_keys_activated) {
			frm.dashboard.set_headline(
				__(
					"Please print the attached INI letter, send it to your bank and wait for confirmation. Then verify the bank keys.",
				),
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
								description: __(
									"Set a new password for downloading bank statements from your bank.",
								),
							},
							{
								fieldname: "store_passphrase",
								label: __("Store Passphrase"),
								fieldtype: "Check",
								default: 1,
								description: __(
									"Store the passphrase in the ERPNext database to enable automated, regular download of bank statements.",
								),
							},
							{
								fieldname: "signature_passphrase",
								label: __("Signature Passphrase"),
								fieldtype: "Password",
								description: __(
									"Set a new password for uploading transactions to your bank.",
								),
							},
							{
								fieldname: "info",
								fieldtype: "HTML",
								options: __(
									"Note: When you lose these passwords, you will have to go through the initialization process with your bank again.",
								),
							},
						],
						(values) => {
							frappe.call({
								type: "POST",
								method:
									"banking.ebics.doctype.ebics_user.ebics_user.initialize",
								args: { ebics_user: frm.doc.name, ...values },
								freeze: true,
								freeze_message: __("Initializing..."),
								callback: () => frm.reload_doc(),
							});
						},
						__("Initialize EBICS User"),
						__("Initialize"),
					);
				},
				frm.doc.initialized ? __("Actions") : null,
			);
		}

		if (
			frm.doc.initialized &&
			(!frm.doc.bank_keys_activated || frappe.boot.developer_mode)
		) {
			frm.add_custom_button(
				__("Verify Bank Keys"),
				async () => {
					let passphrase = null;
					if (!frm.doc.passphrase) {
						passphrase = await ask_for_passphrase();
					}

					const bank_keys = await get_bank_keys(frm.doc.name, passphrase);
					if (!bank_keys) {
						return;
					}

					const message = __(
						"Please confirm that the following keys are identical to the ones mentioned on your bank's letter:",
					);
					frappe.confirm(
						`<p>${message}</p>
						<pre>${bank_keys}</pre>`,
						async () => {
							await confirm_bank_keys(frm.doc.name, passphrase);
							frm.reload_doc();
						},
					);
				},
				frm.doc.bank_keys_activated ? __("Actions") : null,
			);
		}

		if (frm.doc.initialized && frm.doc.bank_keys_activated) {
			frm.add_custom_button(__("Download Bank Statements"), () => {
				download_bank_statements(frm.doc.name, !frm.doc.passphrase);
			});

			frm.add_custom_button(
				__("Change Protocol Version"),
				() => {
					const options = [
						{
							label: __("Ebics 2.5 (H004)"),
							value: "H004",
						},
						{
							label: __("Ebics 3.0 (H005)"),
							value: "H005",
						},
					].filter((option) => option.value !== frm.doc.protocol_version);

					frappe.prompt(
						[
							{
								fieldname: "protocol_version",
								label: __("Protocol Version"),
								fieldtype: "Select",
								options: options,
								default: options.length == 1 ? options[0].value : null,
								reqd: true,
							},
							...(frm.doc.passphrase
								? []
								: [
										{
											fieldname: "passphrase",
											label: __("Passphrase"),
											fieldtype: "Password",
											reqd: true,
										},
								  ]),
						],
						(values) => {
							frappe.call({
								type: "PUT",
								method:
									"banking.ebics.doctype.ebics_user.ebics_user.change_protocol_version",
								args: {
									ebics_user: frm.doc.name,
									protocol_version: values.protocol_version,
									passphrase: values.passphrase,
								},
								callback: () => frm.reload_doc(),
							});
						},
						__("Change Protocol Version"),
						__("Change"),
					);
				},
				__("Actions"),
			);
		}
	},
});

function ask_for_passphrase() {
	return new Promise((resolve) => {
		frappe.prompt(
			[
				{
					fieldname: "passphrase",
					label: __("Passphrase"),
					fieldtype: "Password",
					reqd: true,
				},
			],
			(values) => {
				resolve(values.passphrase);
			},
			__("Enter Passphrase"),
			__("Continue"),
		);
	});
}

async function get_bank_keys(ebics_user, passphrase) {
	try {
		return await frappe.xcall(
			"banking.ebics.doctype.ebics_user.ebics_user.download_bank_keys",
			{ ebics_user: ebics_user, passphrase: passphrase },
		);
	} catch (e) {
		frappe.show_alert({
			message: e || __("An error occurred"),
			indicator: "red",
		});
	}
}

async function confirm_bank_keys(ebics_user, passphrase) {
	try {
		await frappe.xcall(
			"banking.ebics.doctype.ebics_user.ebics_user.confirm_bank_keys",
			{ ebics_user: ebics_user, passphrase: passphrase },
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
	const dialog = frappe.prompt(
		[
			{
				fieldname: "from_date",
				label: __("From Date"),
				fieldtype: "Date",
				default: frappe.datetime.now_date(),
				onchange: () => {
					const from_date = dialog.get_value("from_date");
					const empty_disclaimer = __(
						"If no <a href='/app/bank-transaction' target='_blank'>Bank Transactions</a> are created, please check the <a href='/app/error-log' target='_blank'>Error Logs</a>. If there are no errors, the bank likely did not provide any (new) bank statements for this period.",
					);
					if (from_date == frappe.datetime.now_date()) {
						dialog.set_df_property(
							"note",
							"options",
							__(
								"We'll try to download new transactions from today, using <code>camt.052</code>.",
							) + `<br><br>${empty_disclaimer}`,
						);
					} else {
						dialog.set_df_property(
							"note",
							"options",
							__(
								"We'll try to download all transactions of completed days in the selected period, using <code>camt.053</code>.",
							) + `<br><br>${empty_disclaimer}`,
						);
					}
				},
			},
			{
				fieldname: "to_date",
				label: __("To Date"),
				fieldtype: "Date",
				default: frappe.datetime.now_date(),
			},
			...(needs_passphrase
				? [
						{
							fieldname: "passphrase",
							label: __("Passphrase"),
							fieldtype: "Password",
							reqd: true,
						},
				  ]
				: []),
			{
				fieldname: "note",
				fieldtype: "HTML",
			},
		],
		async (values) => {
			try {
				await frappe.xcall(
					"banking.ebics.doctype.ebics_user.ebics_user.download_bank_statements",
					{
						ebics_user: ebics_user,
						from_date: values.from_date,
						to_date: values.to_date,
						passphrase: values.passphrase,
					},
				);
				frappe.show_alert({
					message: __(
						"Bank statements are being downloaded in the background.",
					),
					indicator: "blue",
				});
			} catch (e) {
				frappe.show_alert({
					message: e || __("An error occurred"),
					indicator: "red",
				});
			}
		},
		__("Download Bank Statements"),
		__("Download"),
	);
}
