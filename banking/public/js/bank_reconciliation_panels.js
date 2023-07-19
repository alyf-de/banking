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
		if (!this.doc.bank_account) {
			frappe.throw(__("Please select a Bank Account"));
		}
		// let page_length = 20;
		// let start = (page - 1) * page_length;

		let transactions = await frappe.call({
			method:
				"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_bank_transactions",
			args: {
				bank_account: this.doc.bank_account,
				from_date: this.doc.bank_statement_from_date,
				to_date: this.doc.bank_statement_to_date
			},
			freeze: true,
			freeze_message: __("Fetching Bank Transactions"),
		}).then(response => response.message);
		return transactions;
	}

	render_panels() {
		this.render_list_panel();
		this.render_actions_panel();
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

		new frappe.ui.SortSelector({
			parent: this.$sort_area.find(".sort-by-selector"),
			args: {
				sort_by: 'date',
				sort_order: 'desc',
				options: [
					{fieldname: 'date', label: __('Date')},
					{fieldname: 'amount', label: __('Amount')},
					{fieldname: 'unallocated', label: __('Unallocated Amount')}
				]
			},
			change: function(sort_by, sort_order) {
				// TODO: trigger re-render of list
				console.log(sort_by, sort_order);
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
					<div>
						<span class="bt-label"> ${__("Date: ")} </span>
						<span><b>${transaction.date}</b></span>
					</div>

					<div class="d-flex">
						<div class="w-50">
							<span class="bt-label"> ${__("To Allocate: ")} </span>
							<span class="text-blue">
								${format_currency(transaction.unallocated_amount, transaction.currency)}
							</span>
						</div>
						<div class="w-50 bt-amount-contianer">
							<span class="bt-amount ${transaction.withdrawal ? 'text-danger' : 'text-success'}">
								<b>${symbol} ${format_currency(amount, transaction.currency)}</b>
							</span>
						</div>
					</div>

					<div class="${transaction.description ? '' : 'hide'}">
						<span class="bt-label"> ${__("Description: ")} </span>
						<span>${transaction.description}</span>
					</div>

					<div class="${transaction.reference_number ? '' : 'hide'}">
						<span class="bt-label"> ${__("Reference: ")} </span>
						<span><b>${transaction.reference_number || "--"}</b></span>
					</div>

					<div class="${(transaction.party || transaction.party_type) ? '' : 'hide'}">
						<span class="bt-label"> ${__(transaction.party_type || "") + ": "} </span>
						<span><b>${transaction.party || "--"}</b></span>
					</div>

					<div>
						<span class="bt-label"> ${__("ID: ")} </span>
						<span>${transaction.name}</span>
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