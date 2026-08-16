// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Reconciliation Rule", {
	refresh(frm) {
		frappe.require("bank_reconciliation_rule_stats.bundle.js", () => {
			if (!frm.stats_manager) {
				frm.stats_manager =
					new banking.bank_reconciliation.BankReconciliationRuleStatsManager(
						frm,
					);
			}
			const stats = frm.stats_manager;

			frm.trigger("set_target_account_query");
			frm.remove_custom_button(__("Open Matches"));
			frm.remove_custom_button(__("Reapply to Unreconciled"));
			const filters_json =
				frm.doc.filters && frm.doc.filters !== "[]" ? frm.doc.filters : "[]";

			let has_filters;
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
			if (frm.doc.docstatus === 1 && !frm.doc.disabled && has_filters) {
				frm.add_custom_button(__("Reapply to Unreconciled"), () => {
					frm.trigger("reapply_to_unreconciled");
				});
			}

			if (stats.needs_filter_rerender()) {
				frm.trigger("render_bt_filters");
			} else {
				stats.fetch_and_show();
			}
		});
	},
	async reapply_to_unreconciled(frm) {
		const { message: preview } = await frm.call({
			method: "reapply_to_unreconciled",
			doc: frm.doc,
			args: { dry_run: 1 },
			freeze: true,
			freeze_message: __("Counting matching Bank Transactions..."),
		});
		const count = preview?.count || 0;
		if (!count) {
			frappe.msgprint({
				title: __("Reapply Rule"),
				message: __("No unreconciled Bank Transactions match this rule."),
				indicator: "blue",
			});
			return;
		}

		frappe.confirm(
			__(
				"Apply this rule to {0} unreconciled Bank Transaction(s)? This will create Journal Entries and cannot be undone easily.",
				[`<b>${count}</b>`]
			),
			async () => {
				const { message: result } = await frm.call({
					method: "reapply_to_unreconciled",
					doc: frm.doc,
					args: { dry_run: 0 },
					freeze: true,
					freeze_message: __("Reapplying rule..."),
				});
				const parts = [
					__("Applied: {0}", [result.applied || 0]),
					__("Skipped: {0}", [result.skipped || 0]),
					__("Failed: {0}", [result.failed || 0]),
				];
				frappe.msgprint({
					title: __("Reapply Rule"),
					message: parts.join("<br>"),
					indicator: result.failed ? "orange" : "green",
				});
			}
		);
	},
	bank_account(frm) {
		frm.trigger("set_target_account_query");
		frm.stats_manager?.schedule_fetch();
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
			"account",
		);

		if (!account) {
			frappe.throw(
				__("In {0} {1} the field {2} is not set.", [
					frappe.bold(__("Bank Account")),
					frm.doc.bank_account,
					__("Company Account"),
				]),
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
					stats.schedule_fetch();
				},
			});

			stats.filter_group = filter_group;

			const after_filters_ready = () => {
				if (frm.doc.docstatus !== 0) {
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
							(f) => () => filter_group.add_filter(f[0], f[1], f[2], f[3]),
						),
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
