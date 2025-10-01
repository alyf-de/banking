frappe.ui.form.on("Supplier", {
	setup(frm) {
		frm.make_methods = frm.make_methods || {};
		frm.make_methods["Bank Account"] = () => frm.trigger("make_bank_account");
	},
	make_bank_account(frm) {
		banking.utils
			.create_party_bank_account("Supplier", frm.doc.name)
			.then(() => {
				frappe.show_alert({
					message: __("Supplier Bank Account was created."),
					indicator: "green",
				});
			})
			.catch(() => {
				frappe.show_alert({
					message: __("Supplier Bank Account was not created."),
					indicator: "yellow",
				});
			});
	},
});
