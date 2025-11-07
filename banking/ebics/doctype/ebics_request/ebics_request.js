// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("EBICS Request", {
	refresh: function (frm) {
		if (!frm.is_new() && frm.doc.response.includes("{")) {
			frm.add_custom_button(__("Download response files"), () => {
				frm.trigger("download_files");
			});

			frm.add_custom_button(__("Re-Import"), () => {
				frm.trigger("re_import");
			});
		}
	},
	download_files: function (frm) {
		window.open(
			`/api/method/banking.ebics.doctype.ebics_request.ebics_request.download_files?name=${encodeURIComponent(
				frm.doc.name
			)}`
		);
	},
	re_import: function (frm) {
		frm
			.call({
				doc: frm.doc,
				method: "re_import",
				freeze: true,
				freeze_message: __("Re-importing EBICS transactions ..."),
			})
			.then(() => {
				frappe.show_alert({
					message: __("EBICS transactions re-imported successfully."),
					indicator: "green",
				});
			})
			.catch(() => {
				frappe.show_alert({
					message: __("Failed to re-import EBICS transactions."),
					indicator: "red",
				});
			});
	},
});
