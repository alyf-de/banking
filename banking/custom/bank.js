frappe.ui.form.on("Bank", {
	refresh: function (frm) {
		if (frm.doc.ebics_host_id && frm.doc.ebics_url) {
			frm.add_custom_button(
				__("Show Protocol Versions"),
				() => {
					frappe.call({
						method: "banking.custom.bank.get_protocol_versions",
						args: {
							bank_name: frm.doc.name,
						},
						callback: (r) => {
							frappe.msgprint({
								title: __("EBICS Protocol Versions"),
								message: JSON.stringify(r.message, null, 2),
							});
						},
					});
				},
				"EBICS"
			);
		}
	},
});
