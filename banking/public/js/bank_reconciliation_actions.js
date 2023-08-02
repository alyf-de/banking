frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.ActionsPanel = class ActionsPanel {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		this.init_actions_container();
		this.render_tabs();
		this.$actions_container.find("#match_voucher-tab").trigger("click");
	}

	init_actions_container() {
		if (this.$wrapper.find(".actions-panel").length > 0) {
			this.$actions_container = this.$wrapper.find(".actions-panel");
			this.$actions_container.empty();
		} else {
			this.$actions_container = this.$wrapper.append(`
				<div class="actions-panel"></div>
			`).find(".actions-panel");
		}

		this.$actions_container.append(`
			<div class="form-tabs-list">
				<ul class="nav form-tabs" role="tablist" aria-label="Action Tabs">
				</ul>
			</div>

			<div class="tab-content p-10"></div>
		`);
	}

	render_tabs() {
		this.tabs_list_ul = this.$actions_container.find(".form-tabs");
		this.$tab_content = this.$actions_container.find(".tab-content");

		["Details", "Match Voucher", "Create Voucher"].forEach(tab => {
			let tab_name = frappe.scrub(tab);
			this.add_tab(tab_name, tab);

			let $tab_link = this.tabs_list_ul.find(`#${tab_name}-tab`);
			$tab_link.on("click", () => {
				if (tab == "Details") {
					this.details_section();
				} else if (tab == "Match Voucher") {
					this.match_section();
				}
			});
		});
	}

	add_tab(tab_name, tab) {
		this.tabs_list_ul.append(`
			<li class="nav-item">
				<a class="nav-actions-link"
					id="${tab_name}-tab" data-toggle="tab"
					href="#" role="tab" aria-controls="${tab}"
				>
					${__(tab)}
				</a>
			</li>
		`);
	}

	details_section() {
		this.$tab_content.empty();
		this.set_detail_tab_fields();
		this.details_field_group = new frappe.ui.FieldGroup({
			fields: this.details_fields,
			body: this.$tab_content,
			card_layout: true,
		});
		this.details_field_group.make();
	}

	async match_section() {
		this.$tab_content.empty();
		this.match_field_group = new frappe.ui.FieldGroup({
			fields: this.get_actions_panel_fields(),
			body: this.$tab_content,
			card_layout: true,
		});
		this.match_field_group.make();

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

		let vouchers = await this.get_matching_vouchers(document_types);
		this.render_data_table(vouchers);

		let transaction_amount = this.transaction.withdrawal || this.transaction.deposit;
		this.render_transaction_amount_summary(
			flt(transaction_amount),
			flt(this.transaction.unallocated_amount),
			this.transaction.currency,
		);
	}

	render_data_table(vouchers) {
		this.summary_data = {};
		let table_data = vouchers.map((row) => {
			return [
				row[1],
				row[2],
				row[5] || row[8], // Reference Date
				format_currency(row[3], row[9]),
				row[4] || '',
				row[6] || '',
			];
		});

		const datatable_options = {
			columns: this.get_data_table_columns(),
			data: table_data,
			dynamicRowHeight: true,
			checkboxColumn: true,
			inlineFilters: true,
			events: {
				onCheckRow: (row) => this.check_data_table_row(row)
			}
		};


		this.actions_table = new frappe.DataTable(
			this.match_field_group.get_field("vouchers").$wrapper[0],
			datatable_options
		);

		// Highlight first row
		this.actions_table.style.setStyle(
			".dt-cell[data-row-index='0']", {backgroundColor: '#F4FAEE'}
		);
	}

	check_data_table_row(row) {
		if (!row) return;

		let id = row[1].content;
		let value = this.get_amount_from_row(row);

		// If `id` in summary_data, remove it (row was unchecked), else add it
		if (id in this.summary_data) {
			delete this.summary_data[id];
		} else {
			this.summary_data[id] = value;
		}

		// Total of selected row amounts in summary_data
		let total_allocated = Object.values(this.summary_data).reduce(
			(a, b) => a + b, 0
		);

		// Deduct allocated amount from transaction's unallocated amount
		// to show the final effect on reconciling
		let transaction_amount = this.transaction.withdrawal || this.transaction.deposit;
		let unallocated = flt(this.transaction.unallocated_amount) - flt(total_allocated);

		this.render_transaction_amount_summary(
			flt(transaction_amount), unallocated, this.transaction.currency,
		);
	}

	render_transaction_amount_summary(total_amount, unallocated_amount, currency) {
		let summary_field = this.match_field_group.get_field("transaction_amount_summary").$wrapper;
		summary_field.empty();

		let allocated_amount = flt(total_amount) - flt(unallocated_amount);

		new erpnext.accounts.bank_reconciliation.SummaryCard({
			$wrapper: summary_field,
			values: {
				"Amount": [total_amount],
				"Allocated Amount": [allocated_amount],
				"To Allocate": [
					unallocated_amount,
					(unallocated_amount < 0 ? "text-danger" : unallocated_amount > 0 ? "text-blue" : "text-success")
				]
			},
			currency: currency,
			wrapper_class: "reconciliation-summary"
		});
	}

	async get_matching_vouchers(document_types) {
		let vouchers = await frappe.call({
			method:
				"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_linked_payments",
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

	update_bank_transaction() {
		var me = this;
		const reference_number = this.details_field_group.get_value("reference_number");
		const party = this.details_field_group.get_value("party");
		const party_type = this.details_field_group.get_value("party_type");

		if (!reference_number && !party && !party_type) return;
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

				this.transaction = {  // Update the transaction in memory
					...this.transaction,
					reference_number: reference_number,
					party_type: party_type,
					party: party,
				}

				frappe.show_alert(
					__("Bank Transaction {0} updated", [me.transaction.name])
				);
			},
		});
	}

	reconcile_selected_vouchers() {
		let selected_map = this.actions_table.rowmanager.checkMap;
		let voucher_rows = this.actions_table.getRows();

		let selected_vouchers = [];
		selected_map.forEach((value, idx) => {
			if (value === 1) {
				let row = voucher_rows[idx];
				selected_vouchers.push({
					payment_doctype: row[2].content,
					payment_name: row[3].content,
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

				let doc = response.message;
				let unallocated_amount = flt(doc.unallocated_amount);
				if (unallocated_amount > 0) {
					// if partial update this.transaction, re-click on list row
					frappe.show_alert({
						message: __("Bank Transaction {0} Partially Matched", [this.transaction.name]),
						indicator: "blue"
					});
					this.panel_manager.refresh_transaction(unallocated_amount);
				} else {
					frappe.show_alert({
						message: __("Bank Transaction {0} Matched", [this.transaction.name]),
						indicator: "green"
					});
					this.panel_manager.move_to_next_transaction();
				}
			},
		});
	}

	get_amount_from_row(row) {
		let value = row[5].content;
		return flt(value.split(" ") ? value.split(" ")[1] : 0);
	}

	get_actions_panel_fields() {
		return [
			{
				label: __("Payment Entry"),
				fieldname: "payment_entry",
				fieldtype: "Check",
				default: 1,
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Journal Entry"),
				fieldname: "journal_entry",
				fieldtype: "Check",
				default: 1,
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
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Sales Invoice"),
				fieldname: "sales_invoice",
				fieldtype: "Check",
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
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Loan Disbursement"),
				fieldname: "loan_disbursement",
				fieldtype: "Check",
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
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				label: __("Bank Transaction"),
				fieldname: "bank_transaction",
				fieldtype: "Check",
				onchange: () => {
					this.populate_matching_vouchers();
				}
			},
			{
				fieldtype: "Section Break"
			},
			{
				label: __("Show Only Exact Amount"),
				fieldname: "exact_match",
				fieldtype: "Check",
				onchange: () => {
					this.populate_matching_vouchers();
				}
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
				fieldname: "reconcile",
				fieldtype: "Button",
				primary: true,
				click: () => {
					this.reconcile_selected_vouchers();
				}
			}
		];
	}

	set_detail_tab_fields() {
		this.details_fields =  [
			{
				label: __("ID"),
				fieldname: "name",
				fieldtype: "Link",
				options: "Bank Transaction",
				default: this.transaction.name,
				read_only: 1,
			},
			{
				label: __("Date"),
				fieldname: "date",
				fieldtype: "Date",
				default: this.transaction.date,
				read_only: 1,
			},
			{
				label: __("Deposit"),
				fieldname: "deposit",
				fieldtype: "Currency",
				default: this.transaction.deposit,
				read_only: 1,
			},
			{
				label: __("Withdrawal"),
				fieldname: "withdrawal",
				fieldtype: "Currency",
				default: this.transaction.withdrawal,
				read_only: 1,
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Description"),
				fieldname: "description",
				fieldtype: "Small Text",
				default: this.transaction.description,
				read_only: 1,
			},
			{
				label: __("To Allocate"),
				fieldname: "unallocated_amount",
				fieldtype: "Currency",
				options: "account_currency",
				default: this.transaction.unallocated_amount,
				read_only: 1,
			},
			{
				label: __("Currency"),
				fieldname: "account_currency",
				fieldtype: "Link",
				options: "Currency",
				read_only: 1,
				default: this.transaction.currency,
				hidden: 1,
			},
			{
				label: __("Account Holder"),
				fieldname: "account",
				fieldtype: "Data",
				default: this.transaction.bank_party_name,
				read_only: 1,
				hidden: this.transaction.bank_party_name ? 0 : 1,
			},
			{
				label: __("Party Account Number"),
				fieldname: "account_number",
				fieldtype: "Data",
				default: this.transaction.bank_party_account_number,
				read_only: 1,
				hidden: this.transaction.bank_party_account_number ? 0 : 1,
			},
			{
				label: __("Party IBAN"),
				fieldname: "iban",
				fieldtype: "Data",
				default: this.transaction.bank_party_iban,
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
				default: this.transaction.reference_number,
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Party Type"),
				fieldname: "party_type",
				fieldtype: "Link",
				options: "DocType",
				get_query: function () {
					return {
						filters: {
							name: [
								"in", Object.keys(frappe.boot.party_account_types),
							],
						},
					};
				},
				onchange: () => {
					let value = this.details_field_group.get_value("party_type");
					this.details_field_group.get_field("party").df.options = value;
				},
				default: this.transaction.party_type || null,
			},
			{
				label: __("Party"),
				fieldname: "party",
				fieldtype: "Link",
				options: this.transaction.party_type || null,
			},
			{
				fieldtype: "Section Break"
			},
			{
				label: __("Hidden field for alignment"),
				fieldname: "hidden_field",
				fieldtype: "Data",
				hidden: 1
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Submit"),
				fieldtype: "Button",
				primary: true,
				click: () => this.update_bank_transaction(),
			}
		];
	}

	get_data_table_columns() {
		return [
			{
				name: __("Document Type"),
				editable: false,
				width: 125,
			},
			{
				name: __("Document Name"),
				editable: false,
				width: 1,
			},
			{
				name: __("Reference Date"),
				editable: false,
				width: 120,
			},
			{
				name: __("Remaining"),
				editable: false,
				width: 100,
			},
			{
				name: __("Reference Number"),
				editable: false,
				width: 200,
			},
			{
				name: __("Party"),
				editable: false,
				width: 100,
			},
		];
	}
}