frappe.provide("banking.bank_reconciliation");

banking.bank_reconciliation.OnHoldTab = class OnHoldTab {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		this.panel_manager.actions_tab = "on_hold-tab";
		this.field_group = new frappe.ui.FieldGroup({
			fields: this.get_fields(),
			body: this.actions_panel.$tab_content,
			card_layout: true,
			doc: this.transaction,
		});
		this.field_group.make();
	}

	get_fields() {
		return [
			{
				label: __("On Hold Until"),
				fieldname: "on_hold_until",
				fieldtype: "Date",
				reqd: 1,
			},
			{
				label: __("Set On Hold"),
				fieldname: "set_on_hold",
				fieldtype: "Button",
				primary: true,
				click: () => this.set_on_hold(),
			},
			{ fieldtype: "Section Break", label: __("Request Invoice") },
			{
				label: __("Recipient Type"),
				fieldname: "recipient_type",
				fieldtype: "Select",
				options: "User\nContact\nEmployee",
				default: "Employee",
				reqd: 1,
			},
			{
				label: __("Recipient"),
				fieldname: "recipient",
				fieldtype: "Dynamic Link",
				options: "recipient_type",
				reqd: 1,
			},
			{
				label: __("Request Invoice"),
				fieldname: "request_invoice",
				fieldtype: "Button",
				click: () => this.request_invoice(),
			},
		];
	}

	set_on_hold() {
		const on_hold_until = this.field_group.get_value("on_hold_until");
		if (on_hold_until) {
			this.call("set_bank_transaction_on_hold", { on_hold_until });
		}
	}

	request_invoice() {
		const recipient_type = this.field_group.get_value("recipient_type");
		const recipient = this.field_group.get_value("recipient");
		if (recipient_type && recipient) {
			this.call("request_invoice", { recipient_type, recipient });
		}
	}

	call(method, args) {
		frappe.call({
			method: `banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.${method}`,
			args: { bank_transaction_name: this.transaction.name, ...args },
			freeze: true,
			callback: (response) => {
				if (!response.exc) {
					this.panel_manager.reload_transactions();
				}
			},
		});
	}
};
