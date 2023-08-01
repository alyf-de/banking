frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.PanelManager = class PanelManager {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		this.init_panels();
	}

	async init_panels() {
		this.transactions = await this.get_bank_transactions();

		this.$wrapper.empty();
		this.$panel_wrapper = this.$wrapper.append(`
			<div class="panel-container d-flex"></div>
		`).find(".panel-container");

		this.render_panels()
	}

	async get_bank_transactions() {
		let transactions = await frappe.call({
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_bank_transactions",
			args: {
				bank_account: this.doc.bank_account,
				from_date: this.doc.bank_statement_from_date,
				to_date: this.doc.bank_statement_to_date,
				order_by: this.order || "date asc",
			},
			freeze: true,
			freeze_message: __("Fetching Bank Transactions"),
		}).then(response => response.message);
		return transactions;
	}

	render_panels() {
		if (!this.transactions || !this.transactions.length) {
			this.render_no_transactions();
		} else {
			this.render_list_panel();

			let first_transaction = this.transactions[0];
			this.$list_container.find("#" + first_transaction.name).click();
		}
	}

	render_no_transactions() {
		this.$panel_wrapper.append(`
			<div class="no-transactions">
				<img src="/assets/frappe/images/ui-states/list-empty-state.svg" alt="Empty State">
				<p>${__("No Transactions found for the current filters.")}</p>
			</div>
		`);
	}

	render_list_panel() {
		this.$panel_wrapper.append(`
			<div class="list-panel">
				<div class="sort-by"></div>
				<div class="list-container"></div>
			</div>
		`);

		this.render_sort_area();
		this.render_transactions_list();
	}

	render_actions_panel() {
		this.actions_panel =  new erpnext.accounts.bank_reconciliation.ActionsPanel({
			$wrapper: this.$panel_wrapper,
			transaction: this.active_transaction,
			doc: this.doc
		})
	}

	render_sort_area() {
		this.$sort_area = this.$panel_wrapper.find(".sort-by");
		this.$sort_area.append(`
			<div class="sort-by-title"> ${__("Sort By")} </div>
			<div class="sort-by-selector p-10"></div>
		`);

		var me = this;
		new frappe.ui.SortSelector({
			parent: me.$sort_area.find(".sort-by-selector"),
			args: {
				sort_by: me.order_by || "date",
				sort_order: me.order_direction || "asc",
				options: [
					{fieldname: "date", label: __("Date")},
					{fieldname: "withdrawal", label: __("Withdrawal")},
					{fieldname: "deposit", label: __("Deposit")},
					{fieldname: "unallocated_amount", label: __("Unallocated Amount")}
				]
			},
			change: function(sort_by, sort_order) {
				// Globally set the order used in the re-rendering of the list
				me.order_by = (sort_by || me.order_by || "date");
				me.order_direction = (sort_order || me.order_direction || "asc");
				me.order =  me.order_by + " " + me.order_direction;

				// Re-render the list
				me.init_panels();
			}
		});
	}

	render_transactions_list() {
		this.$list_container = this.$panel_wrapper.find(".list-container");

		this.transactions.map(transaction => {
			let amount = transaction.deposit || transaction.withdrawal;
			let symbol = transaction.withdrawal ? "-" : "+";

			let $row = this.$list_container.append(`
				<div id="${transaction.name}" class="transaction-row p-10">
					<!-- Date & Amount -->
					<div class="d-flex">
						<div class="w-50">
							<span class="bt-label"> ${__("Date: ")} </span>
							<span><b>${transaction.date}</b></span>
						</div>

						<div class="w-50 bt-amount-contianer">
							<span class="bt-amount ${transaction.withdrawal ? 'text-danger' : 'text-success'}">
								<b>${symbol} ${format_currency(amount, transaction.currency)}</b>
							</span>
						</div>
					</div>


					<!-- Description, Reference, Party -->
					<div class="${transaction.description ? '' : 'hide'}">
						<span class="bt-label"> ${__("Description: ")} </span>
						<span>${transaction.description}</span>
					</div>

					<div class="${transaction.reference_number ? '' : 'hide'}">
						<span class="bt-label"> ${__("Reference: ")} </span>
						<span><b>${transaction.reference_number}</b></span>
					</div>

					<div class="${transaction.bank_party_name ? '' : 'hide'}">
						<span class="bt-label"> ${__("Account Holder: ")} </span>
						<span><b>${transaction.bank_party_name}</b></span>
					</div>
				</div>
			`).find("#" + transaction.name);

			$row.on("click", () => {
				$row.addClass("active").siblings().removeClass("active");
				this.active_transaction = transaction;
				this.render_actions_panel();
			})
		})
	}
}