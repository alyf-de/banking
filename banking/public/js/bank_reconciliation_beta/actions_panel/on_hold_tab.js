frappe.provide("banking.bank_reconciliation");

const INVOICE_REQUEST_RECIPIENT_TYPES = ["User", "Contact", "Employee"];

const INVOICE_REQUEST_EMAIL_FIELD = {
	User: "email",
	Contact: "email_id",
	Employee: "user_id",
};

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
		this.field_group.set_value("recipient_type", "User");
		this.set_invoice_request_defaults();
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
				fieldtype: "Link",
				options: "DocType",
				get_query: () => ({
					filters: {
						name: ["in", INVOICE_REQUEST_RECIPIENT_TYPES],
					},
				}),
				onchange: () => this.on_recipient_type_change(),
			},
			{
				label: __("Recipient"),
				fieldname: "recipient",
				fieldtype: "Dynamic Link",
				get_options: () => this.field_group.get_value("recipient_type"),
				onchange: () => this.fetch_recipient_email(),
			},
			{
				label: __("Email"),
				fieldname: "recipient_email",
				fieldtype: "Data",
				options: "Email",
				reqd: 1,
			},
			{
				label: __("On Hold Until"),
				fieldname: "invoice_on_hold_until",
				fieldtype: "Date",
			},
			{
				label: __("Request Invoice"),
				fieldname: "request_invoice",
				fieldtype: "Button",
				click: () => this.request_invoice(),
			},
		];
	}

	on_recipient_type_change() {
		this.field_group.set_values({
			recipient: "",
			recipient_email: "",
		});
	}

	async fetch_recipient_email() {
		const recipient_type = this.field_group.get_value("recipient_type");
		const recipient = this.field_group.get_value("recipient");
		if (!recipient_type || !recipient) {
			return;
		}

		const email_fieldname = INVOICE_REQUEST_EMAIL_FIELD[recipient_type];
		if (!email_fieldname) {
			return;
		}

		const { message } = await frappe.db.get_value(
			recipient_type,
			recipient,
			email_fieldname,
		);
		let email = message?.[email_fieldname];
		if (recipient_type === "Employee" && email) {
			const user = await frappe.db.get_value("User", email, "email");
			email = user.message?.email || email;
		}

		if (email) {
			this.field_group.set_value("recipient_email", email);
		}
	}

	set_invoice_request_defaults() {
		frappe.call({
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_invoice_request_defaults",
			callback: (response) => {
				const defaults = response.message || {};
				if (defaults.recipient_type) {
					this.field_group.set_value("recipient_type", defaults.recipient_type);
				}
				if (defaults.on_hold_until) {
					this.field_group.set_value(
						"invoice_on_hold_until",
						defaults.on_hold_until,
					);
				}
			},
		});
	}

	set_on_hold() {
		const on_hold_until = this.field_group.get_value("on_hold_until");
		if (on_hold_until) {
			this.call("set_bank_transaction_on_hold", { on_hold_until });
		}
	}

	request_invoice() {
		const recipient_email = this.field_group.get_value("recipient_email");
		if (!recipient_email) {
			frappe.msgprint({
				message: __("Email is required."),
				indicator: "orange",
			});
			return;
		}

		const invoice_on_hold_until = this.field_group.get_value(
			"invoice_on_hold_until",
		);
		this.call("request_invoice", {
			recipient_email,
			on_hold_until: invoice_on_hold_until || null,
		});
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
