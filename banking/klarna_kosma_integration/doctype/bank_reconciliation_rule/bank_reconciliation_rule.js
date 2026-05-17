// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

class BankReconciliationRuleStatsManager {
	constructor(frm) {
		this.frm = frm;
		this.request_id = 0;
		this.$stats_el = null;
		this.filter_group = null;
		this._debounced_fetch = null;
		this.rendered_for = null;
	}

	teardown() {
		this.filter_group = null;
		this.$stats_el = null;
		this.rendered_for = null;
	}

	needs_filter_rerender() {
		if (!this.host_is_live() || !this.filter_group) {
			return true;
		}
		if (this.rendered_for !== this.frm.docname) {
			return true;
		}
		// Submitted rules disable filter controls; duplicate as draft must rebuild editable UI.
		if (
			this.frm.doc.docstatus === 0 &&
			this.frm.fields_dict?.filter_area?.$wrapper?.find(
				".form-control:disabled"
			).length
		) {
			return true;
		}
		return false;
	}

	static filters_to_route_options(filters) {
		const by_field = {};
		for (const row of filters) {
			if (!Array.isArray(row) || row.length < 4) {
				continue;
			}
			const field = row[1];
			const op = row[2];
			const value = row[3];
			(by_field[field] ||= []).push([op, value]);
		}
		const opts = {};
		for (const [field, conditions] of Object.entries(by_field)) {
			if (conditions.length === 1) {
				const [op, value] = conditions[0];
				opts[field] = op === "=" ? value : [op, value];
			} else {
				opts[field] = conditions.map(([op, value]) =>
					JSON.stringify([op, value])
				);
			}
		}
		return opts;
	}

	merge_list_filters(user_filters) {
		const merged = user_filters.map((row) => row.slice(0, 4));
		merged.push([
			"Bank Transaction",
			"bank_account",
			"=",
			this.frm.doc.bank_account,
		]);
		return merged;
	}

	open_bank_transaction_list() {
		if (!this.frm.doc.bank_account) {
			frappe.throw(__("Set a Bank Account first."));
		}
		const user_filters = this.get_user_filters();
		if (!user_filters.length) {
			frappe.throw(__("Please define at least one filter."));
		}
		const merged = this.merge_list_filters(user_filters);
		frappe.route_options =
			BankReconciliationRuleStatsManager.filters_to_route_options(merged);
		frappe.set_route("List", "Bank Transaction");
	}

	host_is_live() {
		const parent = this.frm.fields_dict?.filter_area?.$wrapper;
		if (!parent?.length || !this.$stats_el?.length) {
			return false;
		}
		return $.contains(parent[0], this.$stats_el[0]);
	}

	get_user_filters() {
		if (this.filter_group) {
			try {
				const from_ui = this.filter_group.get_filters() || [];
				if (from_ui.length) {
					return from_ui;
				}
			} catch (e) {
				// fall through to saved filters
			}
		}
		try {
			const parsed = JSON.parse(this.frm.doc.filters || "[]");
			return Array.isArray(parsed) ? parsed : [];
		} catch (e) {
			return [];
		}
	}

	get_debounced_fetch() {
		if (!this._debounced_fetch) {
			this._debounced_fetch = frappe.utils.debounce(
				() => this.fetch_and_show(),
				400
			);
		}
		return this._debounced_fetch;
	}

	async fetch_and_show() {
		const $el = this.$stats_el;
		if (!$el?.length || !this.host_is_live()) {
			return;
		}

		if (!this.frm.doc.bank_account) {
			$el.html(
				`<p class="text-muted small mb-0">${__(
					"Set a Bank Account to see match counts."
				)}</p>`
			);
			return;
		}

		let user_filters = [];
		try {
			user_filters = this.get_user_filters();
		} catch (e) {
			user_filters = [];
		}

		if (!user_filters.length) {
			$el.html(
				`<p class="text-muted small mb-0">${__(
					"Add at least one filter to see match counts."
				)}</p>`
			);
			return;
		}

		const request_id = ++this.request_id;
		if (!$el.text().trim()) {
			$el.html(`<p class="text-muted small mb-0">${__("Updating...")}</p>`);
		}

		const filters_str = JSON.stringify(user_filters);
		const method =
			"banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule.get_bank_transaction_match_stats";

		let data;
		try {
			const res = await frappe.call({
				method,
				args: {
					bank_account: this.frm.doc.bank_account,
					filters: filters_str,
					...(!this.frm.is_new() && this.frm.doc.name
						? { bank_reconciliation_rule: this.frm.doc.name }
						: {}),
				},
			});
			data = res.message;
		} catch (e) {
			if (request_id === this.request_id) {
				$el.html(
					`<p class="text-danger small mb-0">${__(
						"Could not load match counts."
					)}</p>`
				);
			}
			return;
		}

		if (request_id !== this.request_id) {
			return;
		}

		const title = __("Submitted Bank Transactions matching this rule:");
		const counts = __(
			"{0} in the last 30 days, {1} in the last 12 months (365 days).",
			[String(data.last_30_days), String(data.last_12_months)]
		);

		$el.html(
			`<p class="text-muted small mb-0"><strong>${frappe.utils.escape_html(
				title
			)}</strong> ${frappe.utils.escape_html(counts)}</p>`
		);
	}

	mount(parent) {
		this.$stats_el = $('<div class="brr-match-stats form-group"></div>');
		parent.append(this.$stats_el);
		this.fetch_and_show();
	}
}

frappe.ui.form.on("Bank Reconciliation Rule", {
	refresh(frm) {
		if (!frm.stats_manager) {
			frm.stats_manager = new BankReconciliationRuleStatsManager(frm);
		}
		const stats = frm.stats_manager;

		frm.trigger("set_target_account_query");
		frm.remove_custom_button(__("Open Matches"));
		const filters_json =
			frm.doc.filters && frm.doc.filters !== "[]" ? frm.doc.filters : "[]";
		let has_filters = false;
		try {
			has_filters = JSON.parse(filters_json).length > 0;
		} catch (e) {
			has_filters = false;
		}
		if (frm.doc.bank_account && has_filters) {
			frm.add_custom_button(__("Open Matches"), () => {
				stats.open_bank_transaction_list();
			});
		}

		if (stats.needs_filter_rerender()) {
			frm.trigger("render_bt_filters");
		} else {
			stats.fetch_and_show();
		}
	},
	bank_account(frm) {
		frm.trigger("set_target_account_query");
		frm.stats_manager?.get_debounced_fetch()();
	},
	async set_target_account_query(frm) {
		if (!frm.doc.bank_account) {
			return;
		}

		const {
			message: { account },
		} = await frappe.db.get_value(
			"Bank Account",
			frm.doc.bank_account,
			"account"
		);

		if (!account) {
			frappe.throw(
				__("In {0} {1} the field {2} is not set.", [
					frappe.bold(__("Bank Account")),
					frm.doc.bank_account,
					__("Company Account"),
				])
			);
		}

		const {
			message: { account_currency: currency, company: company },
		} = await frappe.db.get_value("Account", account, [
			"account_currency",
			"company",
		]);

		frm.set_query("target_account", () => ({
			filters: {
				account_currency: currency,
				company: company,
			},
		}));
	},
	render_bt_filters(frm) {
		const stats = frm.stats_manager;
		stats.teardown();

		const parent = frm.fields_dict.filter_area.$wrapper;
		parent.empty();

		let filters = [];
		try {
			if (frm.doc.filters && frm.doc.filters !== "[]") {
				const parsed = JSON.parse(frm.doc.filters);
				filters = Array.isArray(parsed) ? parsed : [];
			}
		} catch (e) {
			filters = [];
		}

		frappe.model.with_doctype("Bank Transaction", () => {
			const filter_group = new frappe.ui.FilterGroup({
				parent: parent,
				doctype: "Bank Transaction",
				on_change: () => {
					frm.set_value("filters", JSON.stringify(filter_group.get_filters()));
					stats.get_debounced_fetch()();
				},
			});

			stats.filter_group = filter_group;

			const after_filters_ready = () => {
				if (frm.doc.docstatus === 1) {
					parent.find(".filter-action-buttons").remove();
					parent.find(".divider").remove();
					parent.find(".remove-filter").remove();
					parent.find(".form-control").prop("disabled", true);
				}

				stats.rendered_for = frm.docname;
				stats.mount(parent);
			};

			if (filters.length) {
				filter_group.toggle_empty_filters(false);
				frappe
					.run_serially(
						filters.map(
							(f) => () => filter_group.add_filter(f[0], f[1], f[2], f[3])
						)
					)
					.then(() => {
						filter_group.update_filters();
						after_filters_ready();
					})
					.catch(() => {
						after_filters_ready();
					});
			} else {
				after_filters_ready();
			}
		});
	},
});
