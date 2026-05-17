frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.CreateTab = class CreateTab {
	constructor(opts) {
		Object.assign(this, opts);
		this.dimension_fieldnames = [];
		this.make();
	}

	/** Build the create form and append cached accounting dimension fields. */
	make() {
		this.panel_manager.actions_tab = "create_voucher-tab";

		const dimensions = this.accounting_dimensions || [];
		const company_defaults_map = this.accounting_dimension_defaults || {};
		this.dimension_fieldnames = dimensions.map((d) => d.fieldname);

		this.build_field_group();
		this.append_accounting_dimensions(dimensions, company_defaults_map);
	}

	/** Render the main create-voucher fields (without accounting dimensions). */
	build_field_group() {
		this.create_field_group = new frappe.ui.FieldGroup({
			fields: this.get_create_tab_fields(),
			body: this.actions_panel.$tab_content,
			card_layout: true,
		});
		this.create_field_group.make();
	}

	/**
	 * Add the collapsible accounting dimensions section after the base form;
	 * placed above the footer so Create stays at the bottom.
	 */
	append_accounting_dimensions(dimensions, company_defaults_map) {
		if (!this.create_field_group) {
			return;
		}
		const dimension_section = this.build_accounting_dimension_section_fields(
			dimensions,
			company_defaults_map
		);
		if (!dimension_section.length) {
			return;
		}

		this.create_field_group.add_fields(dimension_section);

		const hidden = this.create_field_group.get_field("hidden_field");
		const $footer =
			hidden && hidden.$wrapper && hidden.$wrapper.closest(".form-section");
		const $dim = this.create_field_group.wrapper
			.find(".bank-br-create-accounting-dimensions")
			.closest(".form-section");
		if ($footer && $footer.length && $dim && $dim.length) {
			$dim.insertBefore($footer);
		}

		this.create_field_group.refresh_dependency();

		const dim_section_closed_key =
			"bank-br-create-accounting-dimensions-closed";
		if (dimensions.length) {
			const collapse_default = () => {
				if (localStorage.getItem(dim_section_closed_key) !== null) {
					return;
				}
				const sec =
					this.create_field_group.sections_dict
						?.accounting_dimensions_section ||
					this.create_field_group.sections?.find(
						(s) => s.df?.fieldname === "accounting_dimensions_section"
					);
				if (sec && typeof sec.collapse === "function") {
					sec.collapse(true);
				}
			};
			collapse_default();
			setTimeout(collapse_default, 0);
		}
	}

	/** Field definitions for the accounting dimensions section break and link fields. */
	build_accounting_dimension_section_fields(dimensions, company_defaults_map) {
		const dimension_fields = this.get_accounting_dimension_fields(
			dimensions,
			company_defaults_map
		);
		if (!dimension_fields.length) {
			return [];
		}
		return [
			{
				fieldtype: "Section Break",
				fieldname: "accounting_dimensions_section",
				label: __("Accounting Dimensions"),
				collapsible: 1,
				css_class: "bank-br-create-accounting-dimensions",
			},
			...this.layout_accounting_dimension_fields_two_columns(dimension_fields),
		];
	}

	/** Map ERPNext dimension metadata to Link field definitions with company defaults. */
	get_accounting_dimension_fields(dimensions, company_defaults_map) {
		const defaults_for_company =
			company_defaults_map && this.company && company_defaults_map[this.company]
				? company_defaults_map[this.company]
				: {};
		return (dimensions || []).map((dimension) => {
			const df = {
				fieldname: dimension.fieldname,
				fieldtype: "Link",
				label: __(dimension.label || frappe.model.unscrub(dimension.fieldname)),
				options: dimension.document_type,
			};
			const default_dim = defaults_for_company[dimension.fieldname];
			if (default_dim) {
				df.default = default_dim;
			}
			return df;
		});
	}

	/** Split dimension Link fields across two columns inside the collapsible section. */
	layout_accounting_dimension_fields_two_columns(dimension_fields) {
		if (dimension_fields.length <= 1) {
			return dimension_fields;
		}
		const split_at = Math.ceil(dimension_fields.length / 2);
		return [
			...dimension_fields.slice(0, split_at),
			{
				fieldname: "column_break_accounting_dimensions",
				fieldtype: "Column Break",
			},
			...dimension_fields.slice(split_at),
		];
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

			// Reconcile and update the view
			// when the voucher is submitted in another tab
			frappe.socketio.doc_subscribe(doctype, docname);
			frappe.realtime.off("doc_update");
			frappe.realtime.on("doc_update", (data) => {
				if (data.doctype === doctype && data.name === docname) {
					this.reconcile_new_voucher(doctype, docname);
				}
			});

			frappe.open_in_new_tab = true;
			frappe.set_route("Form", doctype, docname);
		});
	}

	/** Collect non-empty dimension values from the form for the create API call. */
	get_selected_accounting_dimensions(values) {
		const dim_payload = {};
		for (const fn of this.dimension_fieldnames || []) {
			if (values[fn]) {
				dim_payload[fn] = values[fn];
			}
		}
		return dim_payload;
	}

	/**
	 * Create Payment Entry or Journal Entry and run `success_callback`.
	 * Sends selected dimensions as accounting_dimensions JSON for both doctypes.
	 */
	create_voucher_bts(allow_edit = false, success_callback) {
		let values = this.create_field_group.get_values();
		let document_type = values.document_type;
		const dim_payload = this.get_selected_accounting_dimensions(values);
		const accounting_dimensions =
			Object.keys(dim_payload).length > 0 ? JSON.stringify(dim_payload) : null;
		let method =
			"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta";
		let args = {
			bank_transaction_name: this.transaction.name,
			reference_number: values.reference_number,
			reference_date: values.reference_date,
			party_type: values.party_type,
			party: values.party,
			posting_date: values.posting_date,
			mode_of_payment: values.mode_of_payment,
			allow_edit: allow_edit,
			accounting_dimensions: accounting_dimensions,
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

	reconcile_new_voucher(doctype, docname) {
		// If no response, newly created doc is in draft state
		// If deleted in response, newly created doc is deleted
		// If doc object in response, newly created doc is submitted (can be reconciled)
		frappe.call({
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.reconcile_voucher",
			args: {
				transaction_name: this.transaction.name,
				amount: this.transaction.unallocated_amount,
				voucher_type: doctype,
				voucher_name: docname,
			},
			callback: (response) => {
				if (response.exc) {
					frappe.show_alert({
						message: __("Failed to reconcile new {0} against {1}", [
							doctype,
							this.transaction.name,
						]),
						indicator: "red",
					});
					return;
				} else if (
					response.message &&
					Object.keys(response.message).length > 0
				) {
					if (response.message.deleted) {
						frappe.realtime.off("doc_update");
						return;
					}

					this.actions_panel.after_transaction_reconcile(
						response.message,
						true,
						doctype
					);
				}
			},
		});
	}

	get_create_tab_fields() {
		let party_type =
			this.transaction.party_type ||
			(flt(this.transaction.withdrawal) > 0 ? "Supplier" : "Customer");
		return [
			{
				label: __("Document Type"),
				fieldname: "document_type",
				fieldtype: "Select",
				options: `Payment Entry\nJournal Entry`,
				default: "Payment Entry",
				onchange: () => {
					let value = this.create_field_group.get_value("document_type");
					let fields = this.create_field_group;

					fields.get_field("party").df.reqd = value === "Payment Entry";
					fields.get_field("party_type").df.reqd = value === "Payment Entry";
					fields.get_field("journal_entry_type").df.reqd =
						value === "Journal Entry";
					fields.get_field("second_account").df.reqd =
						value === "Journal Entry";

					this.create_field_group.refresh();
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
				fieldname: "edit_in_full_page",
				fieldtype: "Button",
				label: __("Edit in Full Page"),
				click: () => {
					this.edit_in_full_page();
				},
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
				depends_on: "eval: doc.document_type == 'Journal Entry'",
			},
			{
				fieldname: "second_account",
				fieldtype: "Link",
				label: "Account",
				options: "Account",
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
				reqd: 1,
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
				reqd: 1,
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
				label: __("Create"),
				fieldtype: "Button",
				primary: true,
				click: () => this.create_voucher(),
			},
		];
	}
};
