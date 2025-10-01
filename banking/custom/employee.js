frappe.ui.form.on("Employee", {
	setup(frm) {
		frm.make_methods = frm.make_methods || {};
		frm.make_methods["Bank Account"] = () => frm.trigger("make_bank_account");
	},
	make_bank_account(frm) {
		banking.utils
			.create_party_bank_account("Employee", frm.doc.name)
			.then(() => {
				frappe.show_alert({
					message: __("Employee Bank Account was created."),
					indicator: "green",
				});
			})
			.catch(() => {
				frappe.show_alert({
					message: __("Employee Bank Account was not created."),
					indicator: "yellow",
				});
			});
	},
});
