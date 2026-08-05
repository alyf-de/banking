frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.DetailsTab = class DetailsTab {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		this.panel_manager.actions_tab = "details-tab";

		this.details_field_group = new frappe.ui.FieldGroup({
			fields: this.get_detail_tab_fields(),
			body: this.actions_panel.$tab_content,
			card_layout: true,
			doc: this.transaction,
		});
		this.details_field_group.make();
	}

	update_bank_transaction() {
		var me = this;
		const reference_number =
			this.details_field_group.get_value("reference_number");
		const party = this.details_field_group.get_value("party");
		const party_type = this.details_field_group.get_value("party_type");

		if (!this.details_field_group.dirty) {
			frappe.show_alert({
				message: __("No changes to update"),
				indicator: "yellow",
			});
			return;
		}

		frappe.call({
			method:
				"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.update_bank_transaction",
			args: {
				bank_transaction_name: me.transaction.name,
				reference_number: reference_number,
				party_type: party_type,
				party: party,
			},
			freeze: true,
			freeze_message: __("Updating ..."),
			callback: (response) => {
				if (response.exc) {
					frappe.show_alert(__("Failed to update {0}", [me.transaction.name]));
					return;
				}

				// Update transaction
				me.panel_manager.refresh_transaction(
					null,
					reference_number,
					party_type,
					party
				);

				frappe.show_alert(
					__("Bank Transaction {0} updated", [me.transaction.name])
				);
			},
		});
	}

	get_detail_tab_fields() {
		return [
			{
				label: __("ID"),
				fieldname: "name",
				fieldtype: "Link",
				options: "Bank Transaction",
				read_only: 1,
			},
			{
				label: __("Bank Account"),
				fieldname: "bank_account",
				fieldtype: "Link",
				options: "Bank Account",
				read_only: 1,
				hidden: this.frm.doc.bank_account ? 1 : 0,
			},
			{
				label: __("Date"),
				fieldname: "date",
				fieldtype: "Date",
				read_only: 1,
			},
			{
				label: __("Deposit"),
				fieldname: "deposit",
				fieldtype: "Currency",
				options: "currency",
				read_only: 1,
			},
			{
				label: __("Withdrawal"),
				fieldname: "withdrawal",
				fieldtype: "Currency",
				options: "currency",
				read_only: 1,
			},
			{
				label: __("Included Fee"),
				fieldname: "included_fee",
				fieldtype: "Currency",
				options: "currency",
				read_only: 1,
				hidden: flt(this.transaction.included_fee_for_reconciliation) ? 0 : 1,
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Description"),
				fieldname: "description",
				fieldtype: "Small Text",
				read_only: 1,
			},
			{
				label: __("To Allocate"),
				fieldname: "reconcilable_amount",
				fieldtype: "Currency",
				options: "currency",
				read_only: 1,
			},
			{
				label: __("Currency"),
				fieldname: "currency",
				fieldtype: "Link",
				options: "Currency",
				read_only: 1,
				hidden: 1,
			},
			{
				label: __("Account Holder"),
				fieldname: "bank_party_name",
				fieldtype: "Data",
				read_only: 1,
				hidden: this.transaction.bank_party_name ? 0 : 1,
			},
			{
				label: __("Party Account Number"),
				fieldname: "bank_party_account_number",
				fieldtype: "Data",
				read_only: 1,
				hidden: this.transaction.bank_party_account_number ? 0 : 1,
			},
			{
				label: __("Party IBAN"),
				fieldname: "bank_party_iban",
				fieldtype: "Data",
				options: "IBAN",
				read_only: 1,
				hidden: this.transaction.bank_party_iban ? 0 : 1,
			},
			{
				label: __("Update"),
				fieldtype: "Section Break",
				fieldname: "update_section",
			},
			{
				label: __("Reference Number"),
				fieldname: "reference_number",
				fieldtype: "Data",
				onchange: () => this.toggle_save_button(),
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Party Type"),
				fieldname: "party_type",
				fieldtype: "Link",
				options: "DocType",
				get_query: function () {
					return {
						filters: {
							name: ["in", Object.keys(frappe.boot.party_account_types)],
						},
					};
				},
				onchange: () => this.toggle_save_button(),
			},
			{
				label: __("Party"),
				fieldname: "party",
				fieldtype: "Dynamic Link",
				get_options: () => this.details_field_group.get_value("party_type"),
				onchange: () => this.toggle_save_button(),
			},
			{
				fieldtype: "Section Break",
			},
			{
				label: __("Hidden field for alignment"),
				fieldname: "hidden_field",
				fieldtype: "Data",
				hidden: 1,
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Save"),
				fieldname: "save_transaction",
				fieldtype: "Button",
				primary: true,
				hidden: 1,
				click: () => this.update_bank_transaction(),
			},
		];
	}

	toggle_save_button() {
		this.details_field_group.get_field("save_transaction").df.hidden =
			!this.details_field_group.dirty;
		this.details_field_group.refresh();
	}
};
