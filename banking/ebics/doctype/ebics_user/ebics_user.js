// Copyright (c) 2024, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("EBICS User", {
	refresh(frm) {
		frm.add_custom_button(
			__("Initialize"),
			() => {
				frappe.call({
					method: "banking.ebics.doctype.ebics_user.ebics_user.initialize",
					args: { ebics_user: frm.doc.name },
					freeze: true,
					freeze_message: __("Initializing..."),
					callback: () => frm.reload_doc(),
				});
			},
			frm.doc.initialized ? __("Actions") : null
		);

		if (frm.doc.initialized) {
			frm.add_custom_button(
				__("Verify Bank Keys"),
				async () => {
					bank_keys = await get_bank_keys(frm.doc.name);
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
				download_bank_statements(frm.doc.name);
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

function download_bank_statements(ebics_user) {
	frappe.prompt(
		[
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
		],
		async (values) => {
			try {
				await frappe.xcall(
					"banking.ebics.doctype.ebics_user.ebics_user.download_bank_statements",
					{
						ebics_user: ebics_user,
						from_date: values.from_date,
						to_date: values.to_date,
					}
				);
				frappe.show_alert({
					message: __("Bank statements downloaded"),
					indicator: "green",
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
