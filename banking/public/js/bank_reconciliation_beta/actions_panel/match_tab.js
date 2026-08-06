frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.MatchTab = class MatchTab {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	async make() {
		this.panel_manager.actions_tab = "match_voucher-tab";

		this.match_field_group = new frappe.ui.FieldGroup({
			fields: await this.get_match_tab_fields(),
			body: this.actions_panel.$tab_content,
			card_layout: true,
		});
		this.match_field_group.make();

		await this.populate_matching_vouchers();
	}

	summary_empty_state() {
		this.render_transaction_amount_summary(0, 0, 0, this.transaction.currency);
	}

	async populate_matching_vouchers(event_obj) {
		if (event_obj && event_obj.type === "input") {
			// `bind_change_event` in `data.js` triggers both an input and change event
			// This triggers the `populate_matching_vouchers` twice on clicking on filters
			// Since the input event is debounced, we can ignore it for a checkbox
			return;
		}

		this.summary_empty_state();
		this.render_data_table();
		this.actions_table.freeze();

		let filter_fields = this.match_field_group.get_values();
		let new_filters = Object.keys(filter_fields).filter(
			(field) => filter_fields[field] === 1,
		);

		this.update_filters_in_state(new_filters);

		let vouchers = await this.get_matching_vouchers(new_filters);
		this.set_table_data(vouchers);
		this.actions_table.unfreeze();

		this.render_baseline_summary();
	}

	update_filters_in_state(new_filters) {
		Object.keys(this.panel_manager.actions_filters).map((key) => {
			let value = new_filters.includes(key) ? 1 : 0;
			this.panel_manager.actions_filters[key] = value;
		});
	}

	async get_matching_vouchers(document_types) {
		let vouchers = await frappe
			.call({
				method:
					"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_linked_payments",
				args: {
					bank_transaction_name: this.transaction.name,
					document_types: document_types,
				},
			})
			.then((result) => result.message);
		return vouchers || [];
	}

	render_data_table() {
		const datatable_options = {
			columns: this.get_data_table_columns(),
			data: [],
			dynamicRowHeight: true,
			checkboxColumn: true,
			inlineFilters: true,
			layout: "fluid",
			serialNoColumn: false,
			freezeMessage: __("Loading..."),
		};

		this.actions_table = new frappe.DataTable(
			this.match_field_group.get_field("vouchers").$wrapper[0],
			datatable_options,
		);

		this.bind_row_check_event();
	}

	set_table_data(vouchers) {
		this.summary_data = {};
		let table_data = vouchers.map((row) => {
			return [
				{
					content: row.reference_date || row.posting_date, // Reference Date
					format: (value) => {
						const formatted_date = frappe.format(value, {
							fieldtype: "Date",
						});
						return row.date_match ? formatted_date.bold() : formatted_date;
					},
				},
				{
					content: row.paid_amount,
					currency: row.currency,
					format: (value) => {
						let formatted_value = format_currency(value, row.currency);
						let match_condition =
							row.amount_match || row.unallocated_amount_match;
						return match_condition ? formatted_value.bold() : formatted_value;
					},
				},
				{
					content: row.party,
					format: (value) => {
						if (row.party_name) {
							frappe.utils.add_link_title(
								row.party_type,
								row.party,
								row.party_name,
							);
						}
						let formatted_value = frappe.format(value, {
							fieldtype: "Link",
							options: row.party_type,
						});
						return row.party_match ? formatted_value.bold() : formatted_value;
					},
				},
				{
					content: row.name,
					format: (value) => {
						let formatted_value = frappe.format(value, {
							fieldtype: "Link",
							options: row.doctype,
						});
						return row.name_in_desc_match
							? formatted_value.bold()
							: formatted_value;
					},
					doctype: row.doctype,
				},
				{
					content: row.reference_no || "",
					format: (value) => {
						let reference_match =
							row.reference_number_match || row.ref_in_desc_match;
						return reference_match ? value.bold() : value;
					},
				},
			];
		});

		this.actions_table.refresh(table_data, this.get_data_table_columns());
	}

	bind_row_check_event() {
		// Resistant to row removal on being out of view in datatable
		$(this.actions_table.bodyScrollable).on(
			"click",
			".dt-cell__content input",
			(e) => {
				let idx = $(e.currentTarget).closest(".dt-cell").data().rowIndex;
				let voucher_row = this.actions_table.getRows()[idx];

				this.check_data_table_row(voucher_row);
			},
		);
	}

	check_data_table_row(row) {
		if (!row) return;

		let id = row[this.position_of("Voucher")].content;
		let value = this.get_amount_from_row(row);
		let currency = row[this.position_of("Outstanding")].currency;

		// If `id` in summary_data, remove it (row was unchecked), else add it
		if (id in this.summary_data) {
			delete this.summary_data[id];
		} else {
			this.summary_data[id] = {
				amount: value,
				currency: currency,
				doctype: row[this.position_of("Voucher")].doctype,
			};
		}

		if (this.has_currency_mismatch_selection()) {
			this.render_baseline_summary();
			return;
		}

		// Deposit included fees are only booked against unpaid invoices.
		// PE/JE matching and Create Voucher stay on the bank net amount.
		let unpaid_invoices_only =
			this.panel_manager.actions_filters.unpaid_invoices;
		let allocation_budget =
			erpnext.accounts.bank_reconciliation.get_allocation_budget(
				this.transaction,
				this.summary_data,
				unpaid_invoices_only,
			);
		let total_allocated = Object.values(this.summary_data).reduce(
			(a, entry) => a + entry.amount,
			0,
		);
		let max_allocated = Math.min(total_allocated, allocation_budget);

		let transaction_amount =
			erpnext.accounts.bank_reconciliation.get_summary_amount(
				this.transaction,
				this.summary_data,
				unpaid_invoices_only,
			);
		let unallocated = flt(allocation_budget) - flt(max_allocated);
		let actual_unallocated = flt(allocation_budget) - flt(total_allocated);

		this.render_transaction_amount_summary(
			flt(transaction_amount),
			unallocated,
			actual_unallocated,
			this.transaction.currency,
		);
	}

	has_currency_mismatch_selection() {
		return Object.values(this.summary_data).some(
			(entry) => entry.currency && entry.currency !== this.transaction.currency,
		);
	}

	render_baseline_summary() {
		let transaction_amount =
			this.transaction.withdrawal || this.transaction.deposit;
		this.render_transaction_amount_summary(
			flt(transaction_amount),
			flt(this.transaction.unallocated_amount),
			flt(this.transaction.unallocated_amount),
			this.transaction.currency,
		);
	}

	render_transaction_amount_summary(
		total_amount,
		unallocated_amount,
		actual_unallocated,
		currency,
	) {
		let summary_field = this.match_field_group.get_field(
			"transaction_amount_summary",
		).$wrapper;
		summary_field.empty();

		// Show the actual allocated amount
		let allocated_amount = flt(total_amount) - flt(unallocated_amount);

		new erpnext.accounts.bank_reconciliation.SummaryCard({
			$wrapper: summary_field,
			values: {
				Amount: [total_amount],
				"Allocated Amount": [allocated_amount, ""],
				"To Allocate": [
					unallocated_amount,
					unallocated_amount < 0
						? "text-danger"
						: unallocated_amount > 0
						  ? "text-blue"
						  : "text-success",
					actual_unallocated,
				],
			},
			currency: currency,
			wrapper_class: "reconciliation-summary",
		});
	}

	async reconcile_selected_vouchers() {
		const me = this;
		let selected_vouchers = [];
		let selected_map = this.actions_table.rowmanager.checkMap;
		let voucher_rows = this.actions_table.getRows();

		selected_map.forEach((value, idx) => {
			if (value === 1) {
				const row = voucher_rows[idx];
				selected_vouchers.push({
					payment_doctype: row[this.position_of("Voucher")].doctype,
					payment_name: row[this.position_of("Voucher")].content,
					amount: this.get_amount_from_row(row),
					currency: row[this.position_of("Outstanding")].currency,
					party: row[this.position_of("Party")].content,
					reference_no: row[this.position_of("Reference")].content,
				});
			}
		});

		if (!selected_vouchers.length > 0) {
			frappe.show_alert({
				message: __("Please select at least one voucher to reconcile"),
				indicator: "red",
			});
			return;
		}

		let voucher_types = new Set(
			selected_vouchers.map((voucher) => voucher.payment_doctype),
		);
		if (voucher_types.size > 1) {
			frappe.show_alert({
				message: __("Please select vouchers of the same type to reconcile"),
				indicator: "red",
			});
			return;
		}

		const handlers = await this.frm.script_manager.get_handlers(
			"before_reconcile",
			"Bank Reconciliation Tool Beta",
		);
		let extra_params = {};
		try {
			for (const handler of handlers.new_style) {
				let result = await handler(
					this.frm,
					this.transaction,
					selected_vouchers,
				);
				if (result) {
					extra_params = { ...extra_params, ...result };
				}
			}
		} catch (error) {
			const ignored_errors = new Set([
				"manual_reconcile_cancelled",
				"currency_mismatch_requires_single_voucher",
				"unsupported_voucher_type_for_currency_conversion",
				"missing_reconcile_amount_context",
			]);
			if (!ignored_errors.has(error?.message)) {
				frappe.show_alert({
					message: __("Unable to prepare reconciliation details."),
					indicator: "red",
				});
			}
			return;
		}

		// If the vouchers have different parties prepare a prompt to reconcile multi-party
		let parties = new Set(selected_vouchers.map((voucher) => voucher.party));
		if (parties.size > 1) {
			this.show_multiple_party_reconcile_prompt().then(() => {
				this.bulk_reconcile_vouchers(selected_vouchers, true, extra_params);
			});
		} else {
			this.bulk_reconcile_vouchers(selected_vouchers, false, extra_params);
		}
	}

	bulk_reconcile_vouchers(
		selected_vouchers,
		reconcile_multi_party,
		extra_params,
	) {
		let me = this;
		frappe.call({
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.bulk_reconcile_vouchers",
			args: {
				bank_transaction_name: this.transaction.name,
				vouchers: selected_vouchers,
				reconcile_multi_party: reconcile_multi_party,
				extra_params: extra_params,
			},
			freeze: true,
			freeze_message: __("Reconciling ..."),
			callback: (response) => {
				if (response.exc) {
					frappe.show_alert({
						message: __("Failed to reconcile {0}", [this.transaction.name]),
						indicator: "red",
					});
					return;
				}

				me.actions_panel.after_transaction_reconcile(response.message, false);
			},
		});
	}

	show_multiple_party_reconcile_prompt() {
		return new Promise((resolve, reject) => {
			frappe.confirm(
				__(
					"Are you trying to reconcile vouchers of different parties? This action will reconcile vouchers using a Journal Entry.",
				),
				() => {
					resolve();
				},
				() => {
					reject();
				},
			);
		});
	}

	async get_match_tab_fields() {
		const filters_state = this.panel_manager.actions_filters;
		const document_types = Object.keys(this.panel_manager.document_types);
		const document_types_fields = [];
		document_types.forEach((type, index) => {
			document_types_fields.push({
				label: __(type),
				fieldname: frappe.scrub(type),
				fieldtype: "Check",
				default: filters_state[frappe.scrub(type)],
				onchange: (e) => {
					this.populate_matching_vouchers(e);
				},
			});

			// Add column break after every 2 fields
			if ((index + 1) % 2 === 0 && index !== document_types.length - 1) {
				document_types_fields.push({
					fieldtype: "Column Break",
				});
			}
		});

		const party_title = await frappe.utils.fetch_link_title(
			this.transaction.party_type,
			this.transaction.party,
		);

		return [
			...document_types_fields,
			{
				fieldtype: "Section Break",
			},
			{
				label: __("Only matching amounts"),
				fieldname: "exact_match",
				fieldtype: "Check",
				default: filters_state.exact_match,
				onchange: (e) => {
					this.populate_matching_vouchers(e);
				},
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Only unpaid vouchers"),
				fieldname: "unpaid_invoices",
				fieldtype: "Check",
				default: filters_state.unpaid_invoices,
				onchange: (e) => {
					this.populate_matching_vouchers(e);
				},
				depends_on:
					"eval: doc.sales_invoice || doc.purchase_invoice || doc.expense_claim",
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: this.transaction.party
					? __("Only from {0}", [frappe.utils.escape_html(party_title)])
					: __("Not available"),
				fieldname: "exact_party_match",
				fieldtype: "Check",
				default: this.transaction.party_type && this.transaction.party ? 1 : 0,
				onchange: (e) => {
					this.populate_matching_vouchers(e);
				},
				hidden: !Boolean(this.transaction.party_type && this.transaction.party),
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "transaction_amount_summary",
				fieldtype: "HTML",
			},
			{
				fieldname: "vouchers",
				fieldtype: "HTML",
			},
			{
				fieldtype: "Section Break",
				fieldname: "section_break_reconcile",
				hide_border: 1,
			},
			{
				label: __("Hidden field for alignment"),
				fieldname: "hidden_field_2",
				fieldtype: "Data",
				hidden: 1,
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Reconcile"),
				fieldname: "bt_reconcile",
				fieldtype: "Button",
				primary: true,
				click: () => {
					this.reconcile_selected_vouchers();
				},
			},
		];
	}

	position_of(label) {
		// NOTE: Edit this function if the order of columns in the data table changes
		const column_positions = {
			Date: 1,
			Outstanding: 2,
			Party: 3,
			Voucher: 4,
			Reference: 5,
		};
		return column_positions[label];
	}

	get_data_table_columns() {
		return [
			{
				name: __("Date"),
				editable: false,
			},
			{
				name: __("Outstanding"),
				editable: false,
			},
			{
				name: __("Party"),
				editable: false,
				align: "left",
			},
			{
				name: __("Voucher"),
				editable: false,
				align: "left",
			},
			{
				name: __("Reference"),
				editable: false,
				align: "left",
			},
		];
	}

	get_amount_from_row(row) {
		const amount_position = this.position_of("Outstanding");
		return row[amount_position].content; // Amount
	}
};
