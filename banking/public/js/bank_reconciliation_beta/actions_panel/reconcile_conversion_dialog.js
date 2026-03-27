frappe.provide("erpnext.accounts.bank_reconciliation");

/**
 * Manual reconcile conversion dialog for bank reconciliation.
 *
 * Opens and manages the "Set Reconcile Conversion Amounts" flow, keeps source
 * amount, exchange rate, and target amount synchronized with validation/clamping
 * rules, and updates preview rows for post-reconcile allocation and exchange
 * gain/loss impact.
 */
const RECONCILE_PRECISION = 9;

erpnext.accounts.bank_reconciliation.prompt_manual_reconcile_amounts =
	function (context, transaction, selected_voucher) {
		return new Promise((resolve, reject) => {
			const source_currency = transaction.currency;
			const target_currency = context.voucher_currency;
			const max_source_amount = Math.max(
				0,
				flt(transaction.unallocated_amount)
			);
			const voucher_outstanding_amount = Math.abs(
				flt(selected_voucher?.amount)
			);
			const max_target_amount = voucher_outstanding_amount || 0;
			const prefilled_exchange_rate =
				round_reconcile_value(context.exchange_rate) || 1;

			let initial_source_amount = max_source_amount;
			initial_source_amount = round_reconcile_value(initial_source_amount);

			const initial_target_amount = round_reconcile_value(max_target_amount);
			const is_deposit = flt(transaction.deposit) > 0;

			let is_internal_update = false;
			let dialog;

			const set_dialog_values_safely = async (values) => {
				if (!values || !Object.keys(values).length) {
					return;
				}

				is_internal_update = true;
				try {
					await dialog.set_values(values);
				} finally {
					is_internal_update = false;
				}
			};

			let is_settled = false;
			const resolve_once = (payload) => {
				if (!is_settled) {
					is_settled = true;
					resolve(payload);
				}
			};
			const reject_once = () => {
				if (!is_settled) {
					is_settled = true;
					reject(new Error("manual_reconcile_cancelled"));
				}
			};

			const get_source_amount = () => {
				return clamp_source_amount(
					dialog.get_value("source_amount"),
					max_source_amount
				);
			};
			const get_exchange_rate = () => {
				return sanitize_exchange_rate(dialog.get_value("exchange_rate"));
			};
			const get_target_amount = () => {
				return clamp_target_amount(
					dialog.get_value("target_amount"),
					max_target_amount
				);
			};
			const refresh_previews = (overrides = {}) => {
				const source_amount = overrides.source_amount ?? get_source_amount();
				const exchange_rate = overrides.exchange_rate ?? get_exchange_rate();
				const target_amount = overrides.target_amount ?? get_target_amount();

				update_to_allocate_preview(
					dialog,
					source_amount,
					source_currency,
					max_source_amount
				);
				update_exchange_gain_loss_preview(
					dialog,
					get_exchange_gain_loss_amount(
						source_amount,
						exchange_rate,
						target_amount
					),
					target_currency,
					is_deposit
				);
			};
			const sync_target_with_source_and_rate = async (source_input = null) => {
				const source_amount = get_source_amount();
				const exchange_rate = get_exchange_rate();
				const target_amount = clamp_target_amount(
					source_amount * exchange_rate,
					max_target_amount
				);
				const updates = {};

				if (
					source_input !== null &&
					!same_number(source_input, source_amount)
				) {
					updates.source_amount = source_amount;
				}
				if (!same_number(dialog.get_value("target_amount"), target_amount)) {
					updates.target_amount = target_amount;
				}

				await set_dialog_values_safely(updates);
				refresh_previews({ source_amount, exchange_rate, target_amount });
			};
			const handle_source_amount_change = async () => {
				if (is_internal_update) return;

				const source_input = round_reconcile_value(
					dialog.get_value("source_amount")
				);
				await sync_target_with_source_and_rate(source_input);
			};
			const handle_exchange_rate_change = async () => {
				if (is_internal_update) return;

				await sync_target_with_source_and_rate();
			};
			const handle_target_amount_change = async () => {
				if (is_internal_update) return;

				const target_input = round_reconcile_value(
					dialog.get_value("target_amount")
				);
				const target_amount = clamp_target_amount(
					target_input,
					max_target_amount
				);
				const updates = {};

				if (!same_number(target_input, target_amount)) {
					updates.target_amount = target_amount;
				}

				await set_dialog_values_safely(updates);
				refresh_previews({ target_amount });
			};

			dialog = new frappe.ui.Dialog({
				title: __("Set Reconcile Conversion Amounts"),
				fields: [
					{
						fieldname: "source_amount",
						fieldtype: "Currency",
						label: __("Source Amount ({0})", [source_currency]),
						options: source_currency,
						reqd: 1,
						default: initial_source_amount,
						description: __("Max {0}", [
							format_currency(max_source_amount, source_currency),
						]),
						onchange: handle_source_amount_change,
					},
					{
						fieldtype: "Column Break",
					},
					{
						fieldname: "exchange_rate",
						fieldtype: "Float",
						precision: 9,
						label: __("Exchange Rate"),
						description: __("On {0}", [
							frappe.format(transaction.date, { fieldtype: "Date" }),
						]),
						reqd: 1,
						default: prefilled_exchange_rate,
						onchange: handle_exchange_rate_change,
					},
					{
						fieldtype: "Section Break",
					},
					{
						fieldname: "target_amount",
						fieldtype: "Currency",
						label: __("Target Amount ({0})", [target_currency]),
						options: target_currency,
						reqd: 1,
						default: initial_target_amount,
						description:
							max_target_amount > 0
								? __("Max {0}", [
										format_currency(max_target_amount, target_currency),
								  ])
								: "",
						onchange: handle_target_amount_change,
					},
					{
						fieldtype: "Section Break",
					},
					{
						fieldname: "post_reconcile_to_allocate_preview",
						fieldtype: "HTML",
					},
					{
						fieldname: "exchange_gain_loss_preview",
						fieldtype: "HTML",
					},
				],
				primary_action_label: __("Reconcile"),
				primary_action(values) {
					const source_amount = clamp_source_amount(
						values.source_amount,
						max_source_amount
					);
					const exchange_rate = round_reconcile_value(values.exchange_rate);
					const target_amount = clamp_target_amount(
						values.target_amount,
						max_target_amount
					);

					if (source_amount <= 0 || exchange_rate <= 0 || target_amount <= 0) {
						frappe.show_alert({
							message: __(
								"Source amount, exchange rate, and target amount must be greater than zero."
							),
							indicator: "red",
						});
						return;
					}

					resolve_once({
						manual_reconcile_amounts: {
							source_amount: source_amount,
							exchange_rate: exchange_rate,
							target_amount: target_amount,
							source_currency: source_currency,
							target_currency: target_currency,
						},
					});
					dialog.hide();
				},
				secondary_action_label: __("Cancel"),
				secondary_action() {
					dialog.hide();
				},
			});

			dialog.onhide = () => {
				reject_once();
			};

			dialog.show();
			refresh_previews({
				source_amount: initial_source_amount,
				exchange_rate: prefilled_exchange_rate,
				target_amount: initial_target_amount,
			});
		});
	};

function round_reconcile_value(value) {
	return flt(value, RECONCILE_PRECISION);
}

function sanitize_exchange_rate(value) {
	return Math.max(0, flt(value));
}

function clamp_source_amount(value, max_source_amount) {
	return round_reconcile_value(
		Math.min(Math.max(flt(value), 0), max_source_amount)
	);
}

function clamp_target_amount(value, max_target_amount) {
	const sanitized = Math.max(flt(value), 0);

	return round_reconcile_value(
		max_target_amount > 0 ? Math.min(sanitized, max_target_amount) : sanitized
	);
}

function same_number(a, b) {
	return round_reconcile_value(a) === round_reconcile_value(b);
}

function get_exchange_gain_loss_amount(source, exchange_rate, target) {
	return round_reconcile_value(target - source * exchange_rate);
}

function update_to_allocate_preview(
	dialog,
	source_amount,
	source_currency,
	max_source_amount
) {
	const to_allocate_amount = flt(max_source_amount) - flt(source_amount);
	dialog.get_field("post_reconcile_to_allocate_preview").$wrapper.html(
		`<div class="text-muted small">
				${__("To Allocate after reconcile")}:
				<strong>${format_currency(to_allocate_amount, source_currency)}</strong>
			</div>`
	);
}

function update_exchange_gain_loss_preview(
	dialog,
	exchange_gain_loss_amount,
	target_currency,
	is_deposit
) {
	// For deposits (receipts): positive delta (target > source*rate) means
	// we're writing off more receivable than received → Exchange Loss.
	// For withdrawals (payments): the same positive delta means we settled
	// more liability than we paid out → Exchange Gain.
	const is_exchange_loss = is_deposit
		? exchange_gain_loss_amount > 0
		: exchange_gain_loss_amount < 0;
	const is_exchange_gain = is_deposit
		? exchange_gain_loss_amount < 0
		: exchange_gain_loss_amount > 0;
	const exchange_label = is_exchange_loss
		? __("Exchange Loss")
		: is_exchange_gain
		? __("Exchange Gain")
		: __("Exchange Gain/Loss");
	const display_amount =
		is_exchange_loss || is_exchange_gain
			? Math.abs(exchange_gain_loss_amount)
			: exchange_gain_loss_amount;

	dialog.get_field("exchange_gain_loss_preview").$wrapper.html(
		`<div class="small text-muted">
				${exchange_label}:
				<strong>${format_currency(display_amount, target_currency)}</strong>
			</div>`
	);
}
