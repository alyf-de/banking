// Copyright (c) 2022, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Klarna Kosma Session', {
	refresh: function(frm) {
		if (frm.doc.status === "Running" && frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("End Session"), () => {
				frm.call({
					doc: frm.doc,
					method: "end_kosma_session",
					freeze: true,
					freeze_message: __("Ending Session ..."),
				}).then(() => {
					frm.reload_doc();
					frappe.show_alert({message: __("Session Ended"), indicator: "green"})
				});
			})
		}
	}
});
