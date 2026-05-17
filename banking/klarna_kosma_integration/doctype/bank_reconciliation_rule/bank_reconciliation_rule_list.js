// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.listview_settings["Bank Reconciliation Rule"] = {
	add_fields: ["docstatus", "disabled", "priority"],
	has_indicator_for_draft: true,

	get_indicator: function (doc) {
		// Submitted documents
		if (doc.docstatus === 1) {
			if (doc.disabled === 1) {
				return [__("Disabled"), "orange", "disabled,=,1"];
			} else {
				return [__("Active"), "green", "docstatus,=,1"];
			}
		}

		// Draft documents
		if (doc.docstatus === 0) {
			return [__("Draft"), "blue", "docstatus,=,0"];
		}
	},

	onload: function (listview) {
		if (!frappe.model.can_write("Bank Reconciliation Rule")) {
			return;
		}
		listview.page.add_inner_button(__("Reorder by Priority"), () =>
			banking_brr_open_reorder_dialog(listview)
		);
	},
};

function banking_brr_open_reorder_dialog(listview) {
	frappe.call({
		method:
			"banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule.get_bank_accounts_with_rules",
		callback(r) {
			const accounts = r.message || [];
			if (!accounts.length) {
				frappe.msgprint({
					title: __("Reorder by Priority"),
					message: __("No bank accounts with reconciliation rules."),
					indicator: "orange",
				});
				return;
			}
			banking_brr_show_reorder_dialog(listview, accounts);
		},
	});
}

function banking_brr_show_reorder_dialog(listview, bank_accounts_with_rules) {
	let sortable = null;

	const dialog = new frappe.ui.Dialog({
		title: __("Reorder bank reconciliation rules"),
		fields: [
			{
				fieldname: "info",
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"The first row is handled first when several rules match. Drag to change the order (priority)."
				)}</p>`,
			},
			{
				fieldname: "bank_account",
				fieldtype: "Link",
				label: __("Bank Account"),
				options: "Bank Account",
				reqd: 1,
			},
			{
				fieldname: "rules_list_html",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Save order"),
		primary_action: function () {
			const account = dialog.get_value("bank_account");
			if (!account) {
				return;
			}
			const ul = dialog.$wrapper.find(".brr-reorder__list").get(0);
			if (!ul) {
				frappe.show_alert({
					indicator: "orange",
					message: __("No rules to save."),
				});
				return;
			}
			const ordered = Array.from(ul.querySelectorAll("li[data-name]")).map(
				(li) => li.getAttribute("data-name")
			);
			if (!ordered.length) {
				frappe.show_alert({
					indicator: "orange",
					message: __("No rules to save."),
				});
				return;
			}
			frappe.call({
				type: "POST",
				freeze: true,
				freeze_message: __("Saving..."),
				method:
					"banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule.reorder_bank_reconciliation_rule_priorities",
				args: {
					bank_account: account,
					ordered_names: ordered,
				},
				callback: (r) => {
					if (!r.exc) {
						banking_brr_reset_sortable();
						dialog.hide();
						listview.refresh();
					}
				},
			});
		},
	});

	function banking_brr_reset_sortable() {
		if (sortable) {
			try {
				sortable.destroy();
			} catch (e) {
				// ignore
			}
		}
		sortable = null;
	}

	function banking_brr_render(rules) {
		const $wrap = dialog.fields_dict.rules_list_html.$wrapper;
		$wrap.empty();
		if (!rules || !rules.length) {
			$wrap.html(
				`<p class="text-muted">${__("No rules for this bank account.")}</p>`
			);
			return;
		}
		const items = rules
			.map((r) => {
				const name = frappe.utils.escape_html(r.name);
				const ta = r.target_account
					? " — " + frappe.utils.escape_html(r.target_account)
					: "";
				const p = Number(r.priority) || 0;
				const st =
					Number(r.docstatus) === 0
						? "draft"
						: Number(r.disabled)
						? "disabled"
						: "submitted";
				return `<li class="brr-reorder__item" data-name="${name}" data-priority-st="${st}">
					<span class="brr-reorder__handle">${frappe.utils.icon(
						"drag",
						"xs",
						"",
						"",
						"sortable-handle"
					)}</span>
					<span class="brr-reorder__label"><strong>${name}</strong>${ta}</span>
					<span class="text-muted small brr-reorder__prio">P ${p}</span>
				</li>`;
			})
			.join("");

		$wrap.html(
			`<ul class="brr-reorder__list unstyled list-unstyled">${items}</ul><style>
				.brr-reorder-dialog .brr-reorder__item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border: 1px solid var(--border-color, #d1d8dd); border-radius: var(--border-radius, 4px); margin-bottom: 4px; background: var(--control-bg, #fff); font-size: var(--text-md); }
				.brr-reorder__handle { cursor: grab; color: var(--text-muted); }
				.brr-reorder__label { flex: 1; }
				.brr-reorder__item[data-priority-st="disabled"] { opacity: 0.7; }
			</style>`
		);
	}

	function banking_brr_init_sortable() {
		if (typeof Sortable === "undefined") {
			frappe.msgprint(
				__(
					"Sortable is not available. Please open the dialog from the Bank Reconciliation Rule list and try again."
				)
			);
			return;
		}
		const el = dialog.$wrapper.find(".brr-reorder__list").get(0);
		if (!el) {
			return;
		}
		banking_brr_reset_sortable();
		sortable = new Sortable(el, {
			handle: ".sortable-handle",
			animation: 150,
		});
	}

	function banking_brr_load_rules() {
		const account = dialog.get_value("bank_account");
		if (!account) {
			return;
		}
		banking_brr_reset_sortable();
		dialog.fields_dict.rules_list_html.$wrapper.html(
			`<p class="text-muted">${__("Loading...")}</p>`
		);
		frappe.call({
			type: "GET",
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule.get_rules_for_reorder",
			args: { bank_account: account },
			callback: function (r) {
				if (r.exc) {
					dialog.fields_dict.rules_list_html.$wrapper.html(
						`<p class="text-danger">${__(
							"Failed to load rules. Please try again."
						)}</p>`
					);
					return;
				}
				if (r.message) {
					banking_brr_render(r.message);
					banking_brr_init_sortable();
				}
			},
		});
	}

	dialog.$wrapper.addClass("brr-reorder-dialog");
	dialog.fields_dict.bank_account.get_query = () => ({
		filters: [["Bank Account", "name", "in", bank_accounts_with_rules]],
	});
	dialog.show();
	const $ba = dialog.get_field("bank_account").$input;
	$ba.on("change", () => banking_brr_load_rules());
	$ba.on("awesomplete-selectcomplete", () => banking_brr_load_rules());
	if (bank_accounts_with_rules.length === 1) {
		dialog.set_value("bank_account", bank_accounts_with_rules[0]);
		banking_brr_load_rules();
	}
}
