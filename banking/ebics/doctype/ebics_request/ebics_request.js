// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("EBICS Request", {
	refresh: function (frm) {
		if (!frm.is_new() && frm.doc.response.includes("{")) {
			frm.add_custom_button(__("Download response files"), () => {
				frm.trigger("download_files");
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
});
