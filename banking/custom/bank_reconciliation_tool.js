frappe.ui.form.on("Bank Reconciliation Tool", {
	refresh(frm) {
		if (frm.no_banking_redirect) {
			return;
		}

		frappe.confirm(
			__("Did you mean {0}?", [
				`<strong>${__("Bank Reconciliation Tool Beta")}</strong>`,
			]),
			() => {
				frappe.set_route("Form", "Bank Reconciliation Tool Beta");
			},
			() => {
				frm.no_banking_redirect = true;
			}
		);
	},
});
