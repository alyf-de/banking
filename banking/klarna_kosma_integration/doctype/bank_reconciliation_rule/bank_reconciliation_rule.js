// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

function brr_filters_to_route_options(filters) {
	const opts = {};
	for (const row of filters) {
		if (!Array.isArray(row) || row.length < 4) {
			continue;
		}
		const field = row[1];
		const op = row[2];
		const value = row[3];
		if (Object.prototype.hasOwnProperty.call(opts, field)) {
			continue;
		}
		if (op === "=") {
			opts[field] = value;
		} else {
			opts[field] = [op, value];
		}
	}
	return opts;
}

function brr_merge_list_filters(frm, user_filters) {
	const merged = user_filters.map((row) => row.slice(0, 4));
	merged.push(["Bank Transaction", "bank_account", "=", frm.doc.bank_account]);
	return merged;
}

function brr_open_bank_transaction_list(frm) {
	if (!frm.doc.bank_account) {
		frappe.throw(__("Set a Bank Account first."));
	}
	const user_filters = brr_get_user_filters_for_stats(frm);
	if (!user_filters.length) {
		frappe.throw(__("Please define at least one filter."));
	}
	const merged = brr_merge_list_filters(frm, user_filters);
	frappe.route_options = brr_filters_to_route_options(merged);
	frappe.set_route("List", "Bank Transaction");
}

function brr_stats_host_is_live(frm) {
	const parent = frm.fields_dict?.filter_area?.$wrapper;
	const el = frm._brr_match_stats_$el;
	if (!parent?.length || !el?.length) {
		return false;
	}
	return $.contains(parent[0], el[0]);
}

function brr_get_user_filters_for_stats(frm) {
	let from_ui = [];
	if (frm._bank_transaction_filter_group) {
		try {
			from_ui = frm._bank_transaction_filter_group.get_filters() || [];
		} catch (e) {
			from_ui = [];
		}
	}
	if (from_ui.length) {
		return from_ui;
	}
	try {
		const parsed = JSON.parse(frm.doc.filters || "[]");
		return Array.isArray(parsed) ? parsed : [];
	} catch (e) {
		return [];
	}
}

async function brr_fetch_and_show_match_stats(frm) {
	const $el = frm._brr_match_stats_$el;
	if (!$el || !$el.length || !brr_stats_host_is_live(frm)) {
		return;
	}

	if (!frm.doc.bank_account) {
		$el.html(
			`<p class="text-muted small mb-0">${__(
				"Set a Bank Account to see match counts."
			)}</p>`
		);
		return;
	}

	let user_filters = [];
	try {
		user_filters = brr_get_user_filters_for_stats(frm);
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

	const request_id = (frm._brr_stats_request_id =
		(frm._brr_stats_request_id || 0) + 1);
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
				bank_account: frm.doc.bank_account,
				filters: filters_str,
				...(!frm.is_new() && frm.doc.name
					? { bank_reconciliation_rule: frm.doc.name }
					: {}),
			},
		});
		data = res.message;
	} catch (e) {
		if (request_id === frm._brr_stats_request_id) {
			$el.html(
				`<p class="text-danger small mb-0">${__(
					"Could not load match counts."
				)}</p>`
			);
		}
		return;
	}

	if (request_id !== frm._brr_stats_request_id) {
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

frappe.ui.form.on("Bank Reconciliation Rule", {
	refresh(frm) {
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
				brr_open_bank_transaction_list(frm);
			});
		}

		if (!brr_stats_host_is_live(frm)) {
			frm.trigger("render_bt_filters");
		} else {
			brr_fetch_and_show_match_stats(frm);
		}
	},
	bank_account(frm) {
		frm.trigger("set_target_account_query");
		frm._brr_stats_debounced?.();
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
			if (!frm._brr_stats_debounced) {
				frm._brr_stats_debounced = frappe.utils.debounce(() => {
					brr_fetch_and_show_match_stats(frm);
				}, 400);
			}

			const filter_group = new frappe.ui.FilterGroup({
				parent: parent,
				doctype: "Bank Transaction",
				on_change: () => {
					frm.set_value("filters", JSON.stringify(filter_group.get_filters()));
					frm._brr_stats_debounced?.();
				},
			});

			frm._bank_transaction_filter_group = filter_group;

			const after_filters_ready = () => {
				if (frm.doc.docstatus === 1) {
					parent.find(".filter-action-buttons").remove();
					parent.find(".divider").remove();
					parent.find(".remove-filter").remove();
					parent.find(".form-control").prop("disabled", true);
				}

				const $stats = $('<div class="brr-match-stats form-group"></div>');
				parent.append($stats);
				frm._brr_match_stats_$el = $stats;
				brr_fetch_and_show_match_stats(frm);
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
