frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.ActionsPanel = class ActionsPanel {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		if (this.$wrapper.find(".actions-panel").length > 0) {
			this.$actions_container = this.$wrapper.find(".actions-panel");
			this.$actions_container.empty();
		} else {
			this.$actions_container = this.$wrapper.append(`
				<div class="actions-panel"></div>
			`).find(".actions-panel");
		}

		if (!this.transaction) {
			this.$actions_container.append(`
				<p> Select a transaction to reconcile </p>
			`);
		} else {
			this.render_tabs();
			this.$actions_container.find("#details-tab").trigger("click");
		}
	}

	render_tabs() {
		this.$actions_container.empty();
		this.$tab_content = this.$actions_container.append(`
			<div class="form-tabs-list">
				<ul class="nav form-tabs" role="tablist" aria-label="Action Tabs">
				</ul>
			</div>

			<div class="tab-content p-10">
			</div>
		`).find(".tab-content");

		this.tabs_list_ul = this.$actions_container.find(".form-tabs");
		this.tabs = ["Details", "Match Voucher", "Create Voucher"];
		this.tabs.forEach(tab => {
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
					id="${tab_name}-tab"
					data-toggle="tab"
					href="#"
					role="tab"
					aria-controls="${tab}"
				>
					${__(tab)}
				</a>
			</li>
		`);
	}

	details_section() {
		this.$tab_content.empty();
		this.details_field_group = new frappe.ui.FieldGroup({
			fields: [
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
					label: __("Unallocated Amount"),
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
									"in",
									Object.keys(frappe.boot.party_account_types),
								],
							},
						};
					},
					default: this.transaction.party_type,
				},
				{
					label: __("Party"),
					fieldname: "party",
					fieldtype: "Dynamic Link",
					options: "party_type",
					default: this.transaction.party,
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
					click: () => {
						const reference_number = this.details_field_group.get_value("reference_number");
						const party = this.details_field_group.get_value("party");
						const party_type = this.details_field_group.get_value("party_type");

						if (!reference_number && !party && !party_type) return;

						var me = this;
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
				}
			],
			body: this.$tab_content,
			card_layout: true,
		});
		this.details_field_group.make();
	}

	async match_section() {
		this.$tab_content.empty();
		this.match_field_group = new frappe.ui.FieldGroup({
			fields: [
				{
					label: __("Payment Entry"),
					fieldname: "payment_entry",
					fieldtype: "Check",
					default: 1,
				},
				{
					label: __("Journal Entry"),
					fieldname: "journal_entry",
					fieldtype: "Check",
					default: 1,
				},
				{
					fieldtype: "Column Break"
				},
				{
					label: __("Purchase Invoice"),
					fieldname: "purchase_invoice",
					fieldtype: "Check",
				},
				{
					label: __("Sales Invoice"),
					fieldname: "sales_invoice",
					fieldtype: "Check",
				},
				{
					fieldtype: "Column Break"
				},
				{
					label: __("Loan Repayment"),
					fieldname: "loan_repayment",
					fieldtype: "Check",
				},
				{
					label: __("Loan Disbursement"),
					fieldname: "loan_disbursement",
					fieldtype: "Check",
				},
				{
					fieldtype: "Column Break"
				},
				{
					label: __("Expense Claim"),
					fieldname: "expense_claim",
					fieldtype: "Check",
				},
				{
					label: __("Bank Transaction"),
					fieldname: "bank_transaction",
					fieldtype: "Check",
				},
				{
					fieldtype: "Section Break"
				},
				{
					label: __("Show Only Exact Amount"),
					fieldname: "exact_match",
					fieldtype: "Check",
				},
				{
					fieldtype: "Section Break"
				},
				{
					fieldname: "transaction_amount_summary",
					fieldtype: "HTML",
				},
				{
					label: __("Select Vouchers to Match"),
					fieldname: "matched_vouchers",
					fieldtype: "Table",
					data: this.data,
					in_place_edit: false,
					cannot_delete_rows: true,
					cannot_add_rows: true,
					fields: [
						{
							label: __("Document Type"),
							fieldtype: "Data",
							fieldname: "document_type",
							in_list_view: 1,
							read_only: 1,
						},
						{
							label: __("Document Name"),
							fieldtype: "Data",
							fieldname: "document_name",
							in_list_view: 1,
							read_only: 1,
						},
						{
							label: __("Reference Date"),
							fieldtype: "Data",
							fieldname: "reference_date",
							in_list_view: 1,
							read_only: 1,
						},
						{
							label: __("Remaining"),
							fieldtype: "Data",
							fieldname: "remaining_amount",
							in_list_view: 1,
							read_only: 1,
						},
						{
							label: __("Reference Number"),
							fieldtype: "Data",
							fieldname: "reference_number",
							in_list_view: 1,
							read_only: 1,
						},
						{
							label: __("Party"),
							fieldtype: "Data",
							fieldname: "party",
							in_list_view: 1,
							read_only: 1,
						},
					]
				},
				{
					fieldtype: "Section Break",
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
					fieldtype: "Button",
					primary: true,
					click: () => {
						console.log("Reconcile");
					}
				}
			],
			body: this.$tab_content,
			card_layout: true,
		});
		this.match_field_group.make();

		await this.populate_matching_vouchers();
	}

	async populate_matching_vouchers() {
		let filter_fields = this.match_field_group.get_values();
		let document_types = Object.keys(filter_fields).filter(field => {
			if (field !== "matched_vouchers" && filter_fields[field] === 1) {
				return field;
			}
		});

		let vouchers = await this.get_matching_vouchers(document_types);

		let table_element = this.match_field_group.get_field("matched_vouchers").grid;
		if (vouchers && vouchers.length) {
			let table_data = vouchers.map((row, index) => {
				const reference_date = row[5] ? row[5] : row[8];
				return {
					idx: index + 1,
					name: "row-" + (index + 1),
					document_type: row[1],
					document_name: row[2],
					reference_date: reference_date,
					remaining_amount: format_currency(row[3], row[9]),
					reference_number: row[4],
					party: row[6],
				}
			});

			table_element.df.data = table_data;
			table_element.refresh();
			table_element.grid_rows[0].row.addClass("best-match");

			let transaction_amount = this.transaction.withdrawal || this.transaction.deposit;

			this.render_transaction_amount_summary(
				flt(transaction_amount),
				flt(this.transaction.unallocated_amount),
				this.transaction.currency,
			)
		} else {
			table_element.df.data = [];
			table_element.refresh();
		}
	}

	render_transaction_amount_summary(total_amount, unallocated_amount, currency) {
		let summary_field = this.match_field_group.get_field("transaction_amount_summary").$wrapper;
		let allocated_amount = flt(total_amount) - flt(unallocated_amount);

		new erpnext.accounts.bank_reconciliation.SummaryCard({
			$wrapper: summary_field,
			values: {
				"Amount": [total_amount],
				"Allocated Amount": [allocated_amount],
				"To Allocate": [unallocated_amount, "text-blue"]
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
		return vouchers;
	}
}