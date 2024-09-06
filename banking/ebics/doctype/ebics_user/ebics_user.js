// Copyright (c) 2024, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("EBICS User", {
	refresh(frm) {
		frm.add_custom_button(__("Initialize"), () => {
			frappe.call({
				method: "banking.ebics.doctype.ebics_user.ebics_user.initialize",
				args: { ebics_user: frm.doc.name },
				freeze: true,
				freeze_message: __("Initializing..."),
				callback: () => frm.reload_doc(),
			});
		});
	},
});
