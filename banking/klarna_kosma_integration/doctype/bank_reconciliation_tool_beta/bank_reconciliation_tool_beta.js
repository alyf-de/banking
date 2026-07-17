// Copyright (c) 2023, ALYF GmbH and contributors
// For license information, please see license.txt

const CURRENCY_CONVERSION_SUPPORTED_DOCTYPES = [
	"Sales Invoice",
	"Purchase Invoice",
	"Expense Claim",
];

frappe.ui.form.on("Bank Reconciliation Tool Beta", {
	setup: function (frm) {
		frm.set_query("bank_account", function (doc) {
			return {
				filters: {
					company: doc.company,
					is_company_account: 1,
					bank: doc.bank,
				},
			};
		});

		frm.set_query("bank", function (doc) {
			return {
				query:
					"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.bank_query",
				filters: {
					company: doc.company,
				},
			};
		});
	},

	onload: function (frm) {
		if (!frm.doc.bank_statement_from_date && !frm.doc.bank_statement_to_date) {
			// Set default filter dates
			let today = frappe.datetime.get_today();
			frm.doc.bank_statement_from_date = frappe.datetime.add_months(today, -1);
			frm.doc.bank_statement_to_date = today;
		}

		if (!frm.doc.company) {
			// set default company
			frm.doc.company = frappe.user_defaults.company;
		}
	},

	filter_by_reference_date: function (frm) {
		if (frm.doc.filter_by_reference_date) {
			frm.set_value("bank_statement_from_date", "");
			frm.set_value("bank_statement_to_date", "");
		} else {
			frm.set_value("from_reference_date", "");
			frm.set_value("to_reference_date", "");
		}
	},

	/**
	 * Handles reconcile-time currency conversion for mismatched voucher selections.
	 *
	 * When selected voucher currency matches the bank transaction currency, this
	 * hook exits without altering the default reconcile flow. For currency
	 * mismatches, it enforces single-voucher selection, restricts conversion to
	 * supported voucher types, fetches backend prefill context, and opens the
	 * manual conversion dialog.
	 */
	before_reconcile: async function (frm, transaction, selected_vouchers) {
		const mismatched_vouchers = get_currency_mismatched_vouchers(
			transaction,
			selected_vouchers
		);

		if (!mismatched_vouchers.length) {
			return;
		}

		validate_single_voucher_selection(selected_vouchers);

		const voucher = selected_vouchers[0];
		validate_currency_conversion_voucher_type(voucher);

		const context = await fetch_reconcile_amount_context(transaction, voucher);

		return erpnext.accounts.bank_reconciliation.prompt_manual_reconcile_amounts(
			context,
			transaction,
			voucher
		);
	},

	refresh: function (frm) {
		frm.disable_save();
		frm.fields_dict["filters_section"].collapse(false);

		frm.page.add_action_icon("refresh", () => {
			frm.events.get_bank_transactions(frm);
		});
		frm.change_custom_button_type(__("Get Bank Transactions"), null, "primary");

		frm.page.add_menu_item(__("Auto Reconcile"), function () {
			frappe.confirm(
				__(
					"Auto reconcile bank transactions based on matching reference numbers?"
				),
				() => {
					frappe.call({
						method:
							"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.auto_reconcile_vouchers",
						args: {
							company: frm.doc.company,
							bank: frm.doc.bank,
							bank_account: frm.doc.bank_account,
							from_date: frm.doc.bank_statement_from_date,
							to_date: frm.doc.bank_statement_to_date,
							filter_by_reference_date: frm.doc.filter_by_reference_date,
							from_reference_date: frm.doc.from_reference_date,
							to_reference_date: frm.doc.to_reference_date,
						},
						freeze: true,
						freeze_message: __("Auto Reconciling ..."),
						callback: (r) => {
							if (!r.exc) {
								frm.refresh();
							}
						},
					});
				}
			);
		});

		frm.page.add_menu_item(__("Upload CSV / Excel file"), () =>
			frm.events.route_to_bank_statement_import(frm)
		);

		frm.page.add_menu_item(__("Upload CAMT file"), () =>
			show_camt_uploader(frm)
		);

		frm.page.add_menu_item(__("Upload MT940 file"), () =>
			show_mt940_uploader(frm)
		);

		frm.$reconciliation_area = frm.get_field(
			"reconciliation_action_area"
		).$wrapper;
		frm.events.setup_empty_state(frm);

		frm.events.build_reconciliation_area(frm);
	},

	get_bank_transactions: function (frm) {
		frm.events.build_reconciliation_area(frm);
	},

	route_to_bank_statement_import(frm) {
		frappe.open_in_new_tab = true;

		if (!frm.doc.bank_account || !frm.doc.company) {
			frappe.new_doc("Bank Statement Import");
			return;
		}

		// Route to saved Import Record in new tab
		frappe.call({
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.upload_bank_statement",
			args: {
				dt: frm.doc.doctype,
				dn: frm.doc.name,
				company: frm.doc.company,
				bank_account: frm.doc.bank_account,
			},
			callback: function (r) {
				if (!r.exc) {
					var doc = frappe.model.sync(r.message);
					frappe.open_in_new_tab = true;
					frappe.set_route("Form", doc[0].doctype, doc[0].name);
				}
			},
		});
	},

	company: function (frm) {
		frm.events.get_bank_transactions(frm);
	},

	bank: function (frm) {
		frm.events.get_bank_transactions(frm);
	},

	bank_account: function (frm) {
		if (frm.doc.bank_account) {
			frappe.db.get_value(
				"Bank Account",
				frm.doc.bank_account,
				"account",
				(r) => {
					frappe.db.get_value("Account", r.account, "account_currency", (r) => {
						frm.doc.account_currency = r.account_currency;
						frm.trigger("get_account_opening_balance");
						frm.trigger("get_account_closing_balance");
						frm.trigger("render_summary");
					});
				}
			);
		}

		frm.events.get_bank_transactions(frm);
	},

	bank_statement_from_date: function (frm) {
		frm.trigger("get_account_opening_balance");
		frm.trigger("get_bank_transactions");
	},

	bank_statement_to_date: function (frm) {
		frm.trigger("get_account_closing_balance");
		frm.trigger("render_summary");
		frm.trigger("get_bank_transactions");
	},

	bank_statement_closing_balance: function (frm) {
		frm.trigger("render_summary");
	},

	get_account_opening_balance(frm) {
		if (frm.doc.bank_account && frm.doc.bank_statement_from_date) {
			frappe.call({
				method:
					"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_account_balance",
				args: {
					bank_account: frm.doc.bank_account,
					till_date: frm.doc.bank_statement_from_date,
					company: frm.doc.company,
				},
				callback: (response) => {
					frm.set_value("account_opening_balance", response.message);
				},
			});
		}
	},

	get_account_closing_balance(frm) {
		if (frm.doc.bank_account && frm.doc.bank_statement_to_date) {
			return frappe.call({
				method:
					"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.get_account_balance",
				args: {
					bank_account: frm.doc.bank_account,
					till_date: frm.doc.bank_statement_to_date,
					company: frm.doc.company,
				},
				callback: (response) => {
					frm.cleared_balance = response.message;
				},
			});
		}
	},

	setup_empty_state: function (frm) {
		frm.$reconciliation_area.empty();
		frm.$reconciliation_area.append(`
			<div class="bank-reco-beta-empty-state">
				<p>
					${__("Please select a Bank Account to start reconciling.")}
				</p>
			</div>
		`);
	},

	render_summary: function (frm) {
		// frm.get_field("reconciliation_tool_cards").$wrapper.empty();
		// frappe.require("bank_reconciliation_beta.bundle.js", () => {
		// 	let difference = flt(frm.doc.bank_statement_closing_balance) - flt(frm.cleared_balance);
		// 	let difference_color = difference >= 0 ?  "text-success" : "text-danger";
		// 	frm.summary_card = new erpnext.accounts.bank_reconciliation.SummaryCard({
		// 		$wrapper: frm.get_field("reconciliation_tool_cards").$wrapper,
		// 		values: {
		// 			"Bank Closing Balance": [frm.doc.bank_statement_closing_balance],
		// 			"ERP Closing Balance": [frm.cleared_balance],
		// 			"Difference": [difference, difference_color]
		// 		},
		// 		currency: frm.doc.account_currency,
		// 	})
		// });
	},

	build_reconciliation_area: function (frm) {
		frappe.require("bank_reconciliation_beta.bundle.js", () => {
			if (frm.panel_manager?.cleanup_voucher_watches) {
				frm.panel_manager.cleanup_voucher_watches();
			}
			frm.panel_manager = new erpnext.accounts.bank_reconciliation.PanelManager(
				{
					frm: frm,
					$wrapper: frm.$reconciliation_area,
				}
			);
		});
	},
});

function get_currency_mismatched_vouchers(transaction, selected_vouchers) {
	return (selected_vouchers || []).filter(
		(voucher) => voucher.currency && voucher.currency !== transaction.currency
	);
}

function validate_single_voucher_selection(selected_vouchers) {
	if ((selected_vouchers || []).length === 1) {
		return;
	}

	frappe.show_alert({
		message: __(
			"Currency conversion reconcile is only supported for one voucher at a time."
		),
		indicator: "orange",
	});
	throw new Error("currency_mismatch_requires_single_voucher");
}

function validate_currency_conversion_voucher_type(voucher) {
	if (
		CURRENCY_CONVERSION_SUPPORTED_DOCTYPES.includes(voucher.payment_doctype)
	) {
		return;
	}

	frappe.show_alert({
		message: __(
			"Currency conversion reconcile is only available for Sales Invoice, Purchase Invoice, and Expense Claim."
		),
		indicator: "orange",
	});
	throw new Error("unsupported_voucher_type_for_currency_conversion");
}

async function fetch_reconcile_amount_context(transaction, voucher) {
	const context = await frappe
		.call({
			method:
				"banking.klarna_kosma_integration.doctype.bank_reconciliation_tool_beta.bank_reconciliation_tool_beta.get_reconcile_amount_context",
			args: {
				bank_transaction_name: transaction.name,
				voucher_doctype: voucher.payment_doctype,
				voucher_name: voucher.payment_name,
			},
		})
		.then((result) => result.message);

	if (context) {
		return context;
	}

	frappe.show_alert({
		message: __("Unable to prepare conversion details for reconciliation."),
		indicator: "red",
	});
	throw new Error("missing_reconcile_amount_context");
}

function show_camt_uploader(frm) {
	if (!frm.doc.bank_account) {
		frappe.throw({
			message: __("Please set the 'Bank Account' filter"),
			title: __("Filter Required"),
		});
	}

	const uploader = new frappe.ui.FileUploader({
		dialog_title: __("Upload XML (CAMT.053) file"),
		upload_notes: __("to import bank transactions for {0}.", [
			frm.doc.bank_account,
		]),
		method: "banking.ebics.utils.upload_camt_file",
		doctype: "Bank Account",
		docname: frm.doc.bank_account,
		allow_toggle_private: false,
		allow_take_photo: false,
		allow_web_link: false,
		allow_multiple: false,
		allow_google_drive: false,
		disable_file_browser: true,
		bank_account: frm.doc.bank_account,
		restrictions: {
			allowed_file_types: [".xml", ".XML"],
			max_number_of_files: 1,
		},
	});

	uploader.dialog.$wrapper.on("hidden.bs.modal", () => {
		frm.refresh();
	});
}

function show_mt940_uploader(frm) {
	if (!frm.doc.bank_account) {
		frappe.throw({
			message: __("Please set the 'Bank Account' filter"),
			title: __("Filter Required"),
		});
	}

	const uploader = new frappe.ui.FileUploader({
		dialog_title: __("Upload MT940 file"),
		upload_notes: __("to import bank transactions for {0}.", [
			frm.doc.bank_account,
		]),
		method: "banking.ebics.utils.upload_mt940_file",
		doctype: "Bank Account",
		docname: frm.doc.bank_account,
		allow_toggle_private: false,
		allow_take_photo: false,
		allow_web_link: false,
		allow_multiple: false,
		allow_google_drive: false,
		disable_file_browser: true,
		bank_account: frm.doc.bank_account,
		restrictions: {
			allowed_file_types: [
				".sta",
				".mt940",
				".txt",
				".STA",
				".MT940",
				".940",
				".TXT",
			],
			max_number_of_files: 1,
		},
	});

	uploader.dialog.$wrapper.on("hidden.bs.modal", () => {
		frm.refresh();
	});
}
