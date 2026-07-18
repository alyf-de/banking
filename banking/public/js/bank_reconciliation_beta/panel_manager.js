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
		const dimensions_cached = this.accounting_dimensions != null;
		const document_types_cached = this.document_types != null;
		const cost_center_cached = this.company_default_cost_center != null;

		const [transactions, document_types, dimensions_message, company_defaults] =
			await Promise.all([
				this.get_bank_transactions(),
				document_types_cached
					? Promise.resolve(this.document_types)
					: frappe.xcall(
							"banking.klarna_kosma_integration.doctype.banking_settings.banking_settings.get_doctypes_for_bank_reconciliation",
					  ),
				dimensions_cached
					? Promise.resolve([
							this.accounting_dimensions,
							this.accounting_dimension_defaults,
					  ])
					: this.get_accounting_dimensions(),
				cost_center_cached
					? Promise.resolve(null)
					: frappe.db.get_value("Company", this.frm.doc.company, "cost_center"),
			]);

		this.transactions = transactions;
		if (!document_types_cached) {
			this.document_types = document_types;
		}
		if (!dimensions_cached) {
			this.accounting_dimensions = dimensions_message?.[0] || [];
			this.accounting_dimension_defaults = dimensions_message?.[1] || {};
		}
		if (!cost_center_cached) {
			this.company_default_cost_center =
				company_defaults?.message?.cost_center || "";
		}

		this.$wrapper.empty();
		this.$panel_wrapper = this.$wrapper
			.append(
				`
			<div class="panel-container d-flex"></div>
		`,
			)
			.find(".panel-container");

		this.render_panels();
		this.sync_reserved_voucher_watches();
	}

	/** Re-fetch and re-render the transaction list (e.g. after sort change). */
	async reload_transactions() {
		this.transactions = await this.get_bank_transactions();
		const active_name = this.active_transaction?.name;

		if (!this.transactions?.length) {
			this.active_transaction = null;
			this.$panel_wrapper.empty();
			this.render_no_transactions();
			this.sync_reserved_voucher_watches();
			return;
		}

		if (!this.$list_container?.length) {
			this.$panel_wrapper.empty();
			this.set_actions_panel_default_states();
			this.render_list_panel();
		} else {
			this.$list_container.empty();
			this.render_transactions_list();
		}

		this.sync_reserved_voucher_watches();

		const $row = active_name
			? this.$list_container.find("#" + active_name)
			: $();
		if ($row.length) {
			$row.click();
		} else {
			this.$list_container.find(".transaction-row").first().click();
		}
	}

	/** Load custom accounting dimension metadata once per reco session. */
	async get_accounting_dimensions() {
		const response = await frappe.call({
			method:
				"erpnext.accounts.doctype.accounting_dimension.accounting_dimension.get_dimensions",
			args: {
				with_cost_center_and_project: false,
			},
		});
		return response.message;
	}

	async get_bank_transactions() {
		const transactions = await frappe
			.call({
				method:
					"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_bank_transactions",
				args: {
					company: this.frm.doc.company,
					bank: this.frm.doc.bank,
					bank_account: this.frm.doc.bank_account,
					from_date: this.frm.doc.bank_statement_from_date,
					to_date: this.frm.doc.bank_statement_to_date,
					order_by: this.order || "date asc",
				},
				freeze: true,
				freeze_message: __("Fetching Bank Transactions"),
			})
			.then((response) => response.message);

		return transactions || [];
	}

	render_panels() {
		if (!this.transactions || !this.transactions.length) {
			this.render_no_transactions();
		} else {
			this.set_actions_panel_default_states();
			this.render_list_panel();

			let first_transaction = this.transactions[0];
			this.$list_container.find("#" + first_transaction.name).click();
		}
	}

	set_actions_panel_default_states() {
		// Init actions panel states to store for persistent views
		this.actions_tab = "match_voucher-tab";
		this.actions_filters = Object.fromEntries(
			Object.entries(this.document_types).map(([key, value]) => [
				frappe.scrub(key),
				value ? 1 : 0,
			]),
		);
		this.actions_filters.exact_match = 0;
		this.actions_filters.exact_party_match = 0;
		this.actions_filters.unpaid_invoices = 1;
	}

	render_no_transactions() {
		this.$panel_wrapper.empty();
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
		this.actions_panel =
			new erpnext.accounts.bank_reconciliation.ActionsPanelManager({
				$wrapper: this.$panel_wrapper,
				transaction: this.active_transaction,
				frm: this.frm,
				panel_manager: this,
			});
	}

	/**
	 * Watch a reserved draft voucher until it is submitted or deleted, then reload.
	 * Uses realtime doc_update (primary) plus focus/route checks (fallback).
	 */
	watch_voucher_until_settled(doctype, docname) {
		if (!doctype || !docname) {
			return;
		}

		if (!this._watched_vouchers) {
			this._watched_vouchers = new Map();
		}

		const key = this._voucher_watch_key(doctype, docname);
		if (this._watched_vouchers.has(key)) {
			return;
		}

		this._watched_vouchers.set(key, {
			doctype,
			docname,
			in_flight: false,
		});
		this._subscribe_voucher_doc(doctype, docname);
		this.ensure_voucher_watch_listeners();
	}

	/** Subscribe to every reserved voucher currently in the transaction list. */
	sync_reserved_voucher_watches() {
		const wanted = new Set();
		for (const transaction of this.transactions || []) {
			if (!transaction.reserved_voucher || !transaction.reserved_voucher_type) {
				continue;
			}
			const key = this._voucher_watch_key(
				transaction.reserved_voucher_type,
				transaction.reserved_voucher,
			);
			wanted.add(key);
			this.watch_voucher_until_settled(
				transaction.reserved_voucher_type,
				transaction.reserved_voucher,
			);
		}

		for (const [key, state] of [...(this._watched_vouchers || [])]) {
			if (!wanted.has(key)) {
				this.unwatch_voucher(state.doctype, state.docname);
			}
		}
	}

	_voucher_watch_key(doctype, docname) {
		return `${doctype}::${docname}`;
	}

	_subscribe_voucher_doc(doctype, docname) {
		const open_key = `${doctype}:${docname}`;
		if (frappe.realtime.open_docs?.has(open_key)) {
			return;
		}
		// doc_subscribe throttles to 1/sec via frappe.flags.doc_subscribe (Frappe v15,
		// socketio_client.js). Emit directly while the flag is set so batch voucher watches
		// in the same tick are not dropped after the first subscription.
		if (frappe.flags.doc_subscribe) {
			frappe.realtime.emit("doc_subscribe", doctype, docname);
			frappe.realtime.open_docs.add(open_key);
		} else {
			frappe.realtime.doc_subscribe(doctype, docname);
		}
	}

	unwatch_voucher(doctype, docname) {
		const key = this._voucher_watch_key(doctype, docname);
		if (!this._watched_vouchers?.has(key)) {
			return;
		}
		this._watched_vouchers.delete(key);
		frappe.realtime.doc_unsubscribe(doctype, docname);
	}

	ensure_voucher_watch_listeners() {
		if (this._voucher_watch_bound) {
			return;
		}
		this._voucher_watch_bound = true;

		this._on_voucher_doc_update = (data) => {
			if (!this._voucher_watch_bound) {
				return;
			}
			this.on_voucher_doc_update(data);
		};
		frappe.realtime.on("doc_update", this._on_voucher_doc_update);

		$(window).on("focus.brt_voucher_watch", () => {
			if (!this._voucher_watch_bound) {
				return;
			}
			this.run_voucher_watch_check();
		});
		// frappe.router.off cannot remove a specific handler; guard with _voucher_watch_bound
		this._on_voucher_route_change = () => {
			if (!this._voucher_watch_bound) {
				return;
			}
			const route = frappe.get_route_str();
			if (route.startsWith("Form/Bank Reconciliation Tool Beta")) {
				this.run_voucher_watch_check();
			} else {
				this.cleanup_voucher_watches();
			}
		};
		frappe.router.on("change", this._on_voucher_route_change);
	}

	on_voucher_doc_update(data) {
		if (!data?.doctype || !data?.name || !this._watched_vouchers?.size) {
			return;
		}
		const key = this._voucher_watch_key(data.doctype, data.name);
		if (!this._watched_vouchers.has(key)) {
			return;
		}
		this.check_voucher_settled(data.doctype, data.name);
	}

	async run_voucher_watch_check() {
		if (!this._watched_vouchers?.size) {
			return;
		}
		const watches = [...this._watched_vouchers.values()];
		for (const state of watches) {
			await this.check_voucher_settled(state.doctype, state.docname);
		}
	}

	async check_voucher_settled(doctype, docname) {
		const key = this._voucher_watch_key(doctype, docname);
		const state = this._watched_vouchers?.get(key);
		if (!state || state.in_flight) {
			return;
		}

		state.in_flight = true;
		try {
			const exists = await frappe.db.exists(doctype, docname);
			if (!exists) {
				await this.handle_voucher_settled(doctype, docname);
				return;
			}

			const response = await frappe.db.get_value(doctype, docname, "docstatus");
			const docstatus = cint(response?.message?.docstatus);
			if (docstatus === 1 || docstatus === 2) {
				await this.handle_voucher_settled(doctype, docname);
			}
		} finally {
			const current = this._watched_vouchers?.get(key);
			if (current === state) {
				state.in_flight = false;
			}
		}
	}

	async handle_voucher_settled(doctype, docname) {
		this.unwatch_voucher(doctype, docname);
		await this.reload_transactions_after_voucher_settled();
	}

	async reload_transactions_after_voucher_settled() {
		// Deduplicate socket + focus/route fallback firing together
		if (this._voucher_settled_reload) {
			return this._voucher_settled_reload;
		}
		this._voucher_settled_reload = this.reload_transactions().finally(() => {
			this._voucher_settled_reload = null;
		});
		return this._voucher_settled_reload;
	}

	cleanup_voucher_watches() {
		for (const state of [...(this._watched_vouchers?.values() || [])]) {
			frappe.realtime.doc_unsubscribe(state.doctype, state.docname);
		}
		this._watched_vouchers = new Map();

		if (this._on_voucher_doc_update) {
			frappe.realtime.off("doc_update", this._on_voucher_doc_update);
			this._on_voucher_doc_update = null;
		}
		$(window).off("focus.brt_voucher_watch");
		// Route listener is guarded by _voucher_watch_bound (router.off is unreliable)
		this._voucher_watch_bound = false;
		this._voucher_settled_reload = null;
	}

	clear_voucher_watch() {
		this.cleanup_voucher_watches();
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
					{ fieldname: "date", label: __("Date") },
					{ fieldname: "withdrawal", label: __("Withdrawal") },
					{ fieldname: "deposit", label: __("Deposit") },
					{
						fieldname: "unallocated_amount",
						label: __("Unallocated Amount"),
					},
				],
			},
			change: function (sort_by, sort_order) {
				// Globally set the order used in the re-rendering of the list
				me.order_by = sort_by || me.order_by || "date";
				me.order_direction = sort_order || me.order_direction || "asc";
				me.order = me.order_by + " " + me.order_direction;

				me.reload_transactions();
			},
		});
	}

	render_transactions_list() {
		this.$list_container = this.$panel_wrapper.find(".list-container");

		this.transactions.map((transaction) => {
			let amount = transaction.deposit || transaction.withdrawal;
			let symbol = transaction.withdrawal ? "-" : "+";
			const draft_badge = transaction.reserved_voucher
				? `<span class="indicator-pill yellow filterable no-indicator-dot ellipsis reserved-draft-badge">${__(
						"Draft",
				  )}</span>`
				: "";

			let $row = this.$list_container
				.append(
					`
				<div id="${transaction.name}" class="transaction-row p-10${
					transaction.reserved_voucher ? " is-reserved" : ""
				}">
					<!-- Date & Amount -->
					<div class="d-flex">
						<div class="w-50">
							<span title="${__("Date")}">
								${frappe.format(transaction.date, { fieldtype: "Date" })}
							</span>
							${draft_badge}
						</div>

						<div class="w-50 bt-amount-contianer">
							<span
								title="${__("Amount")}"
								class="bt-amount ${transaction.withdrawal ? "text-danger" : "text-success"}"
							>
								<b>${symbol} ${format_currency(amount, transaction.currency)}</b>
							</span>
						</div>
					</div>


					<!-- Description, Reference, Party -->
					<div
						title="${__("Account Holder")}"
						class="account-holder ${transaction.bank_party_name ? "" : "hide"}"
					>
						<span class="account-holder-value">${transaction.bank_party_name}</span>
					</div>

					<div
						title="${__("Description")}"
						class="description ${transaction.description ? "" : "hide"}"
					>
						<span class="description-value">${transaction.description}</span>
					</div>

					<div
						title="${__("Reference")}"
						class="reference ${transaction.reference_number ? "" : "hide"}"
					>
						<span class="reference-value">${transaction.reference_number}</span>
					</div>
				</div>
			`,
				)
				.find("#" + transaction.name);

			$row.on("click", () => {
				$row.addClass("active").siblings().removeClass("active");

				// this.transaction's objects get updated, we want the latest values
				this.active_transaction = this.transactions.find(
					({ name }) => name === transaction.name,
				);
				this.render_actions_panel();
			});
		});
	}

	refresh_transaction(
		updated_amount = null,
		reference_number = null,
		party_type = null,
		party = null,
	) {
		// Update the transaction object's & view's unallocated_amount **OR** other details
		let id = this.active_transaction.name;
		let current_index = this.transactions.findIndex(({ name }) => name === id);

		let $current_transaction = this.$list_container.find("#" + id);
		let transaction = this.transactions[current_index];

		if (updated_amount) {
			// update amount is > 0 always [src: `after_transaction_reconcile()`]
			this.transactions[current_index]["unallocated_amount"] = updated_amount;
		} else {
			this.transactions[current_index] = {
				...transaction,
				reference_number: reference_number,
				party_type: party_type,
				party: party,
			};
			// Update Reference Number in List
			$current_transaction.find(".reference").removeClass("hide");
			$current_transaction
				.find(".reference-value")
				.text(reference_number || "--");
		}

		$current_transaction.click();
	}

	move_to_next_transaction() {
		// Remove the current transaction from the list and move to the next/previous one
		let id = this.active_transaction.name;
		let $current_transaction = this.$list_container.find("#" + id);
		let current_index = this.transactions.findIndex(({ name }) => name === id);

		let next_transaction = this.transactions[current_index + 1];
		let previous_transaction = this.transactions[current_index - 1];

		if (next_transaction) {
			this.active_transaction = next_transaction;
			let $next_transaction = $current_transaction.next();
			$next_transaction.click();
		} else if (previous_transaction) {
			this.active_transaction = previous_transaction;
			let $previous_transaction = $current_transaction.prev();
			$previous_transaction.click();
		}

		this.transactions.splice(current_index, 1);
		$current_transaction.remove();

		if (!next_transaction && !previous_transaction) {
			this.active_transaction = null;
			this.render_no_transactions();
		}
	}
};
