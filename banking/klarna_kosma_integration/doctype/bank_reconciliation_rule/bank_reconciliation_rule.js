// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bank Reconciliation Rule", {
	refresh(frm) {
		frappe.require("bank_reconciliation_rule_stats.bundle.js", () => {
			if (!frm.stats_manager) {
				frm.stats_manager =
					new banking.bank_reconciliation.BankReconciliationRuleStatsManager(
						frm
					);
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
		});
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
