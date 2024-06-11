frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.MatchTab = class MatchTab {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	async make() {
		this.panel_manager.actions_tab = "match_voucher-tab";

		this.match_field_group = new frappe.ui.FieldGroup({
			fields: this.get_match_tab_fields(),
			body: this.actions_panel.$tab_content,
			card_layout: true,
		});
		this.match_field_group.make()

		this.summary_empty_state();
		await this.populate_matching_vouchers();
	}

	summary_empty_state() {
		let summary_field = this.match_field_group.get_field("transaction_amount_summary").$wrapper;
		summary_field.append(
			`<div class="report-summary reconciliation-summary" style="height: 90px;">
			</div>`
		);
	}

	async populate_matching_vouchers() {
		let filter_fields = this.match_field_group.get_values();
		let document_types = Object.keys(filter_fields).filter(field => filter_fields[field] === 1);

		this.update_filters_in_state(document_types);

		let vouchers = await this.get_matching_vouchers(document_types);
		this.render_data_table(vouchers);

		let transaction_amount = this.transaction.withdrawal || this.transaction.deposit;
		this.render_transaction_amount_summary(
			flt(transaction_amount),
			flt(this.transaction.unallocated_amount),
			0,
			this.transaction.currency,
		);
	}

	update_filters_in_state(document_types) {
		Object.keys(this.panel_manager.actions_filters).map((key) => {
			let value = document_types.includes(key) ? 1 : 0;
			this.panel_manager.actions_filters[key] = value;
		})
	}

	async get_matching_vouchers(document_types) {
		let vouchers = await frappe.call({
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_linked_payments",
			args: {
				bank_transaction_name: this.transaction.name,
				document_types: document_types,
				from_date: this.doc.bank_statement_from_date,
				to_date: this.doc.bank_statement_to_date,
				filter_by_reference_date: this.doc.filter_by_reference_date,
				from_reference_date: this.doc.from_reference_date,
				to_reference_date: this.doc.to_reference_date
			},
		}).then(result => result.message);
		return vouchers || [];
	}

	render_data_table(vouchers) {
		this.summary_data = {};
		let table_data = vouchers.map((row) => {
			return [
				{
					content: row.reference_date || row.posting_date, // Reference Date
					format: (value) => {
						return row.date_match ? value.bold() : value;
					}
				},
				{
					content: row.paid_amount,
					format: (value) => {
						let formatted_value = format_currency(value, row.currency);
						let match_condition =  row.amount_match || row.unallocated_amount_match;
						return match_condition ? formatted_value.bold() : formatted_value;
					}
				},
				{
					content: row.reference_no || '',
					format: (value) => {
						let reference_match = row.reference_number_match || row.name_in_desc_match;
						return reference_match ? value.bold() : value;
					}
				},
				{
					content: row.party,
					format: (value) => {
						let formatted_value =  frappe.format(row.party, {fieldtype: "Link", options: row.party_type});
						return row.party_match ? formatted_value.bold() : formatted_value;
					}
				},
				{
					content: row.name,
					format: (value) => {
						return frappe.format(row.name, {fieldtype: "Link", options: row.doctype});
					},
					doctype: row.doctype,
				},
			];
		});

		const datatable_options = {
			columns: this.get_data_table_columns(),
			data: table_data,
			dynamicRowHeight: true,
			checkboxColumn: true,
			inlineFilters: true,
			layout: "fluid",
			serialNoColumn: false,
		};


		this.actions_table = new frappe.DataTable(
			this.match_field_group.get_field("vouchers").$wrapper[0],
			datatable_options
		);

		// Highlight first row
		this.actions_table.style.setStyle(
			".dt-cell[data-row-index='0']", {backgroundColor: '#F4FAEE'}
		);

		this.bind_row_check_event();
	}

	bind_row_check_event() {
		// Resistant to row removal on being out of view in datatable
		$(this.actions_table.bodyScrollable).on("click", ".dt-cell__content input", (e) => {
			let idx = $(e.currentTarget).closest(".dt-cell").data().rowIndex;
			let voucher_row = this.actions_table.getRows()[idx];

			this.check_data_table_row(voucher_row)
		})
	}

	check_data_table_row(row) {
		if (!row) return;

		let id = row[5].content;  // Voucher name
		let value = this.get_amount_from_row(row);

		// If `id` in summary_data, remove it (row was unchecked), else add it
		if (id in this.summary_data) {
			delete this.summary_data[id];
		} else {
			this.summary_data[id] = value;
		}

		// Total of selected row amounts in summary_data
		// Cap total_allocated to unallocated amount
		let total_allocated = Object.values(this.summary_data).reduce(
			(a, b) => a + b, 0
		);
		let max_allocated = Math.min(total_allocated, this.transaction.unallocated_amount);

		// Deduct allocated amount from transaction's unallocated amount
		// to show the final effect on reconciling
		let transaction_amount = this.transaction.withdrawal || this.transaction.deposit;
		let unallocated = flt(this.transaction.unallocated_amount) - flt(max_allocated);
		let actual_unallocated = flt(this.transaction.unallocated_amount) - flt(total_allocated);

		this.render_transaction_amount_summary(
			flt(transaction_amount), unallocated, actual_unallocated, this.transaction.currency,
		);
	}

	render_transaction_amount_summary(
		total_amount, unallocated_amount, actual_unallocated, currency
	) {
		let summary_field = this.match_field_group.get_field("transaction_amount_summary").$wrapper;
		summary_field.empty();

		let allocated_amount = flt(total_amount) - flt(unallocated_amount);

		new erpnext.accounts.bank_reconciliation.SummaryCard({
			$wrapper: summary_field,
			values: {
				"Amount": [total_amount],
				"Allocated Amount": [allocated_amount, ""],
				"To Allocate": [
					unallocated_amount,
					(unallocated_amount < 0 ? "text-danger" : unallocated_amount > 0 ? "text-blue" : "text-success"),
					actual_unallocated,
				]
			},
			currency: currency,
			wrapper_class: "reconciliation-summary"
		});
	}

	reconcile_selected_vouchers() {
		const me = this;
		let selected_vouchers = [];
		let selected_map = this.actions_table.rowmanager.checkMap;
		let voucher_rows = this.actions_table.getRows();

		selected_map.forEach((value, idx) => {
			if (value === 1) {
				let row = voucher_rows[idx];
				selected_vouchers.push({
					payment_doctype: row[5].doctype,
					payment_name: row[5].content,  // Voucher name
					amount: this.get_amount_from_row(row),
				});
			}
		});

		if (!selected_vouchers.length > 0) {
			frappe.show_alert({
				message: __("Please select at least one voucher to reconcile"),
				indicator: "red"
			});
			return;
		}

		frappe.call({
			method:
				"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.reconcile_vouchers",
			args: {
				bank_transaction_name: this.transaction.name,
				vouchers: selected_vouchers,
			},
			freeze: true,
			freeze_message: __("Reconciling ..."),
			callback: (response) => {
				if (response.exc) {
					frappe.show_alert({
						message: __("Failed to reconcile {0}", [this.transaction.name]),
						indicator: "red"
					});
					return;
				}

				me.actions_panel.after_transaction_reconcile(response.message, false);
			},
		});
	}

	get_match_tab_fields() {
		const filters_state = this.panel_manager.actions_filters;
		return [
			{
				label: __("Payment Entry"),
				fieldname: "payment_entry",
				fieldtype: "Check",
				default: filters_state.payment_entry,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Journal Entry"),
				fieldname: "journal_entry",
				fieldtype: "Check",
				default: filters_state.journal_entry,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Purchase Invoice"),
				fieldname: "purchase_invoice",
				fieldtype: "Check",
				default: filters_state.purchase_invoice,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Sales Invoice"),
				fieldname: "sales_invoice",
				fieldtype: "Check",
				default: filters_state.sales_invoice,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Loan Repayment"),
				fieldname: "loan_repayment",
				fieldtype: "Check",
				default: filters_state.loan_repayment,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Loan Disbursement"),
				fieldname: "loan_disbursement",
				fieldtype: "Check",
				default: filters_state.loan_disbursement,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Expense Claim"),
				fieldname: "expense_claim",
				fieldtype: "Check",
				default: filters_state.expense_claim,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Bank Transaction"),
				fieldname: "bank_transaction",
				fieldtype: "Check",
				default: filters_state.bank_transaction,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				fieldtype: "Section Break"
			},
			{
				label: __("Show Exact Amount"),
				fieldname: "exact_match",
				fieldtype: "Check",
				default: filters_state.exact_match,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Show Exact Party"),
				fieldname: "exact_party_match",
				fieldtype: "Check",
				default: this.transaction.party_type && this.transaction.party ? 1 : 0,
				onchange: () => {
					this.populate_matching_vouchers();
				},
				read_only: !Boolean(this.transaction.party_type && this.transaction.party)
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Unpaid Vouchers"),
				fieldname: "unpaid_invoices",
				fieldtype: "Check",
				default: filters_state.unpaid_invoices,
				onchange: () => {
					this.populate_matching_vouchers();
				},
				depends_on: "eval: doc.sales_invoice || doc.purchase_invoice || doc.expense_claim",
			},
			{
				fieldtype: "Column Break"
			},
			{
				fieldtype: "Section Break"
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
				hidden: 1
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Reconcile"),
				fieldname: "bt_reconcile",
				fieldtype: "Button",
				primary: true,
				click: () => {
					this.reconcile_selected_vouchers();
				}
			}
		];
	}

	get_data_table_columns() {
		return [
			{
				name: __("Date"),
				editable: false,
				format: (value) => {
					return frappe.format(value, {fieldtype: "Date"});
				},
			},
			{
				name: __("Outstanding"),
				editable: false,
			},
			{
				name: __("Reference"),
				editable: false,
				align: "left",
			},
			{
				name: __("Party"),
				editable: false,
			},
			{
				name: __("Voucher"),
				editable: false,
			},
		];
	}

	get_amount_from_row(row) {
		return row[2].content;  // Amount
	}
}