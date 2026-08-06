// Copyright (c) 2025, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.provide("banking.bank_reconciliation");

const REORDER_METHOD_PREFIX =
	"banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule";

banking.bank_reconciliation.open_reorder_dialog = function (listview) {
	frappe.call({
		type: "GET",
		method: `${REORDER_METHOD_PREFIX}.get_bank_accounts_with_rules`,
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
			banking.bank_reconciliation.show_reorder_dialog(listview, accounts);
		},
	});
};

banking.bank_reconciliation.show_reorder_dialog = function (
	listview,
	bank_accounts_with_rules
) {
	let sortable = null;
	let loaded_account = null;

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
				method: `${REORDER_METHOD_PREFIX}.reorder_bank_reconciliation_rule_priorities`,
				args: {
					bank_account: account,
					ordered_names: ordered,
				},
				callback: (r) => {
					if (!r.exc) {
						reset_sortable();
						dialog.hide();
						listview.refresh();
					}
				},
			});
		},
	});

	function reset_sortable() {
		if (sortable) {
			try {
				sortable.destroy();
			} catch (e) {
				// ignore
			}
		}
		sortable = null;
	}

	function rule_status(r) {
		if (Number(r.docstatus) === 0) {
			return "draft";
		}
		if (Number(r.disabled)) {
			return "disabled";
		}
		return "submitted";
	}

	function render(rules) {
		const $wrap = dialog.fields_dict.rules_list_html.$wrapper;
		$wrap.empty();
		if (!rules || !rules.length) {
			$wrap.html(
				`<p class="text-muted">${__("No rules for this bank account.")}</p>`
			);
			return;
		}

		const drag_icon = frappe.utils.icon(
			"drag",
			"xs",
			"",
			"",
			"sortable-handle"
		);
		const items = rules.map((r) =>
			frappe.render_template("reorder_item", {
				name: frappe.utils.escape_html(r.name),
				target_account: r.target_account
					? frappe.utils.escape_html(r.target_account)
					: "",
				priority: Number(r.priority) || 0,
				status: rule_status(r),
				drag_icon,
			})
		);

		$wrap.html(
			`<ul class="brr-reorder__list unstyled list-unstyled">${items.join(
				""
			)}</ul>`
		);
	}

	function init_sortable() {
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
		reset_sortable();
		sortable = new Sortable(el, {
			handle: ".sortable-handle",
			animation: 150,
		});
	}

	function load_rules() {
		const account = dialog.get_value("bank_account");
		if (!account) {
			loaded_account = null;
			return;
		}
		// Link onchange also fires on blur; skip reload when the value did not change
		// (otherwise the first drag loses focus on the Link and destroys Sortable mid-drag).
		if (account === loaded_account) {
			return;
		}
		loaded_account = account;
		reset_sortable();
		dialog.fields_dict.rules_list_html.$wrapper.html(
			`<p class="text-muted">${__("Loading...")}</p>`
		);
		frappe.call({
			type: "GET",
			method: `${REORDER_METHOD_PREFIX}.get_rules_for_reorder`,
			args: { bank_account: account },
			callback: function (r) {
				if (r.exc) {
					loaded_account = null;
					dialog.fields_dict.rules_list_html.$wrapper.html(
						`<p class="text-danger">${__(
							"Failed to load rules. Please try again."
						)}</p>`
					);
					return;
				}
				if (r.message) {
					render(r.message);
					init_sortable();
				}
			},
		});
	}

	dialog.$wrapper.addClass("brr-reorder-dialog");
	dialog.fields_dict.bank_account.get_query = () => ({
		filters: [["Bank Account", "name", "in", bank_accounts_with_rules]],
	});
	dialog.fields_dict.bank_account.df.onchange = () => load_rules();
	dialog.show();
	if (bank_accounts_with_rules.length === 1) {
		dialog.set_value("bank_account", bank_accounts_with_rules[0]);
	}
};
