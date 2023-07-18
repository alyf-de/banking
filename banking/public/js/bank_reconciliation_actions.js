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
				<div class="actions-panel" style="
					width: 55%; height: 70vh; border: 1px solid var(--gray-200);
					height: auto; overflow-y: scroll;
				">
				</div>
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

			<div class="tab-content" style="padding: 10px;">
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
				}
			});
		});
	}

	add_tab(tab_name, tab) {
		this.tabs_list_ul.append(`
			<li class="nav-item">
				<a class="nav-actions-link" id="${tab_name}-tab"
					data-toggle="tab" href="#" role="tab" aria-controls="${tab}"
					style="
						display: block;
						color: var(--text-muted);
						padding: var(--padding-md) 0;
						margin: 0 var(--margin-md);
						text-decoration: none;
					"
				>
					${__(tab)}
				</a>
			</li>
		`);
	}

	details_section() {
		this.$tab_content.empty();
		this.field_group = new frappe.ui.FieldGroup({
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
			],
			body: this.$tab_content,
			card_layout: true,
		});
		this.field_group.make();
	}
}