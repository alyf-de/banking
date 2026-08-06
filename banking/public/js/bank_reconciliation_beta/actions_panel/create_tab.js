frappe.provide("banking.bank_reconciliation");

banking.bank_reconciliation.CreateTab = class CreateTab {
	constructor(opts) {
		Object.assign(this, opts);
		this.accounting_dimensions = (this.accounting_dimensions || []).filter(
			(dimension) => dimension.fieldname && dimension.document_type
		);
		this.custom_dimension_fieldnames = this.accounting_dimensions.map(
			(dimension) => dimension.fieldname
		);
		this.make();
	}

	make() {
		this.panel_manager.actions_tab = "create_voucher-tab";

		if (this.transaction.reserved_voucher) {
			this.render_reserved_draft_link();
			return;
		}

		this.create_field_group = new frappe.ui.FieldGroup({
			fields: this.get_create_tab_fields(),
			body: this.actions_panel.$tab_content,
			card_layout: true,
		});
		this.create_field_group.make();
		this.create_field_group.refresh_section_collapse();
	}

	render_reserved_draft_link() {
		const voucher_type = this.transaction.reserved_voucher_type;
		const voucher_name = this.transaction.reserved_voucher;
		this.panel_manager.watch_voucher_until_settled(voucher_type, voucher_name);
		this.actions_panel.$tab_content.append(`
			<div class="reserved-draft-resume">
				<p class="text-muted">
					${__(
						"A draft {0} is already linked to this transaction. Open it to continue editing or submit.",
						[frappe.utils.escape_html(__(voucher_type))]
					)}
				</p>
				<button type="button" class="btn btn-primary btn-sm open-reserved-draft">
					${__("Open {0}", [frappe.utils.escape_html(voucher_name)])}
				</button>
			</div>
		`);
		this.actions_panel.$tab_content
			.find(".open-reserved-draft")
			.on("click", () => {
				frappe.open_in_new_tab = true;
				frappe.set_route("Form", voucher_type, voucher_name);
			});
	}

	create_voucher() {
		let values = this.create_field_group.get_values();
		let document_type = values.document_type;

		// Create new voucher and delete or refresh current BT row depending on reconciliation
		this.create_voucher_bts(false, (message) =>
			this.actions_panel.after_transaction_reconcile(
				message,
				true,
				document_type
			)
		);
	}

	edit_in_full_page() {
		this.create_voucher_bts(true, (message) => {
			const doc = frappe.model.sync(message);
			let doctype = doc[0].doctype,
				docname = doc[0].name;

			// Reload so the row stays visible with the reserved Draft badge
			this.panel_manager.reload_transactions();
			this.panel_manager.watch_voucher_until_settled(doctype, docname);

			frappe.open_in_new_tab = true;
			frappe.set_route("Form", doctype, docname);
		});
	}

	get_selected_accounting_dimensions(values, fieldnames) {
		const dim_payload = {};
		for (const fieldname of fieldnames || []) {
			if (values[fieldname]) {
				dim_payload[fieldname] = values[fieldname];
			}
		}
		return dim_payload;
	}

	serialize_accounting_dimensions(dim_payload) {
		return Object.keys(dim_payload).length > 0
			? JSON.stringify(dim_payload)
			: null;
	}

	create_voucher_bts(allow_edit = false, success_callback) {
		// Create PE or JV and run `success_callback`
		let values = this.create_field_group.get_values();
		let document_type = values.document_type;
		let method =
			"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta";
		const dim_payload = this.get_selected_accounting_dimensions(
			values,
			this.custom_dimension_fieldnames
		);
		let args = {
			bank_transaction_name: this.transaction.name,
			reference_number: values.reference_number,
			reference_date: values.reference_date,
			party_type: values.party_type,
			party: values.party,
			posting_date: values.posting_date,
			mode_of_payment: values.mode_of_payment,
			allow_edit: allow_edit,
			project: values.project,
			cost_center: values.cost_center,
			accounting_dimensions: this.serialize_accounting_dimensions(dim_payload),
		};

		if (document_type === "Payment Entry") {
			method = method + ".create_payment_entry_bts";
		} else {
			method = method + ".create_journal_entry_bts";
			args = {
				...args,
				entry_type: values.journal_entry_type,
				second_account: values.second_account,
			};
		}

		frappe.call({
			method: method,
			args: args,
			callback: (response) => {
				if (response.exc) {
					frappe.show_alert({
						message: __("Failed to create {0} against {1}", [
							document_type,
							this.transaction.name,
						]),
						indicator: "red",
					});
					return;
				} else if (response.message) {
					success_callback(response.message);
				}
			},
		});
	}

	get_split_accounting_dimension_fields() {
		const company_defaults =
			(this.accounting_dimension_defaults || {})[this.company] || {};
		const to_link_field = (dimension) => {
			const df = {
				fieldname: dimension.fieldname,
				fieldtype: "Link",
				label: __(dimension.label || frappe.model.unscrub(dimension.fieldname)),
				options: dimension.document_type,
			};
			if (company_defaults[dimension.fieldname]) {
				df.default = company_defaults[dimension.fieldname];
			}
			return df;
		};
		const split_at = Math.ceil(this.accounting_dimensions.length / 2);

		return {
			left_custom_dimension_fields: this.accounting_dimensions
				.slice(0, split_at)
				.map(to_link_field),
			right_custom_dimension_fields: this.accounting_dimensions
				.slice(split_at)
				.map(to_link_field),
		};
	}

	persist_create_preference(fieldname) {
		this.panel_manager.create_preferences[fieldname] =
			this.create_field_group.get_value(fieldname);
	}

	apply_document_type_requirements(document_type) {
		const fields = this.create_field_group;
		fields.get_field("party").df.reqd = document_type === "Payment Entry";
		fields.get_field("party_type").df.reqd = document_type === "Payment Entry";
		fields.get_field("journal_entry_type").df.reqd =
			document_type === "Journal Entry";
		fields.get_field("second_account").df.reqd =
			document_type === "Journal Entry";
		fields.refresh();
	}

	get_create_tab_fields() {
		let party_type =
			this.transaction.party_type ||
			(flt(this.transaction.withdrawal) > 0 ? "Supplier" : "Customer");
		const company_defaults =
			(this.accounting_dimension_defaults || {})[this.company] || {};
		const { left_custom_dimension_fields, right_custom_dimension_fields } =
			this.get_split_accounting_dimension_fields();
		const document_type =
			this.panel_manager.create_preferences.document_type || "Payment Entry";
		const is_payment_entry = document_type === "Payment Entry";
		const is_journal_entry = document_type === "Journal Entry";

		return [
			{
				label: __("Document Type"),
				fieldname: "document_type",
				fieldtype: "Select",
				options: `Payment Entry\nJournal Entry`,
				default: document_type,
				onchange: () => {
					this.persist_create_preference("document_type");
					this.apply_document_type_requirements(
						this.create_field_group.get_value("document_type")
					);
				},
			},
			{
				fieldtype: "Section Break",
				fieldname: "details",
				label: "Details",
			},
			{
				fieldname: "reference_number",
				fieldtype: "Data",
				label: __("Reference Number"),
				default:
					this.transaction.reference_number ||
					(this.transaction.description
						? this.transaction.description.slice(0, 140)
						: ""),
			},
			{
				fieldname: "posting_date",
				fieldtype: "Date",
				label: __("Posting Date"),
				reqd: 1,
				default: this.transaction.date,
			},
			{
				fieldname: "reference_date",
				fieldtype: "Date",
				label: __("Cheque/Reference Date"),
				reqd: 1,
				default: this.transaction.date,
			},
			{
				fieldname: "mode_of_payment",
				fieldtype: "Link",
				label: __("Mode of Payment"),
				options: "Mode of Payment",
			},
			{
				fieldname: "column_break_7",
				fieldtype: "Column Break",
			},
			{
				label: __("Journal Entry Type"),
				fieldname: "journal_entry_type",
				fieldtype: "Select",
				options: `Bank Entry\nJournal Entry\nInter Company Journal Entry\nCash Entry\nCredit Card Entry\nDebit Note\nCredit Note\nContra Entry\nExcise Entry\nWrite Off Entry\nOpening Entry\nDepreciation Entry\nExchange Rate Revaluation\nDeferred Revenue\nDeferred Expense`,
				default: "Bank Entry",
				reqd: is_journal_entry,
				depends_on: "eval: doc.document_type == 'Journal Entry'",
			},
			{
				fieldname: "second_account",
				fieldtype: "Link",
				label: "Account",
				options: "Account",
				reqd: is_journal_entry,
				get_query: () => {
					return {
						filters: {
							is_group: 0,
							company: this.company,
						},
					};
				},
				depends_on: "eval: doc.document_type == 'Journal Entry'",
			},
			{
				fieldname: "party_type",
				fieldtype: "Link",
				label: "Party Type",
				options: "DocType",
				reqd: is_payment_entry,
				default: party_type,
				get_query: function () {
					return {
						filters: {
							name: ["in", Object.keys(frappe.boot.party_account_types)],
						},
					};
				},
				onchange: () => {
					let value = this.create_field_group.get_value("party_type");
					this.create_field_group.get_field("party").df.options = value;
				},
			},
			{
				fieldname: "party",
				fieldtype: "Link",
				label: "Party",
				default: this.transaction.party,
				options: party_type,
				reqd: is_payment_entry,
			},
			{
				fieldname: "accounting_dimensions_section",
				fieldtype: "Section Break",
				label: __("Accounting Dimensions"),
				collapsible: 1,
			},
			{
				fieldname: "cost_center",
				fieldtype: "Link",
				label: __("Cost Center"),
				options: "Cost Center",
				default:
					company_defaults.cost_center || this.company_default_cost_center,
				get_query: () => {
					return {
						filters: {
							company: this.company,
							is_group: 0,
						},
					};
				},
			},
			...left_custom_dimension_fields,
			{
				fieldname: "dimension_col_break",
				fieldtype: "Column Break",
			},
			{
				fieldname: "project",
				fieldtype: "Link",
				label: __("Project"),
				options: "Project",
				default: company_defaults.project,
				get_query: () => {
					return {
						filters: {
							company: this.company,
						},
					};
				},
			},
			...right_custom_dimension_fields,
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "edit_in_full_page",
				fieldtype: "Button",
				label: __("Edit in Full Page"),
				click: () => {
					this.edit_in_full_page();
				},
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Create"),
				fieldtype: "Button",
				primary: true,
				click: () => this.create_voucher(),
			},
		];
	}
};
