frappe.provide("erpnext.accounts.bank_reconciliation");

erpnext.accounts.bank_reconciliation.SummaryCard = class SummaryCard {
	/**
	 * {
	 * 	$wrapper: $wrapper,
	 * 	values: {
	 * 		"Amount": [120, "text-blue"],
	 * 		"Allocated Amount": [120, "text-green", 0],
	 * 		"To Allocate": [0, "text-blue", -20 (actual unallocated amount)]
	 * 	},
	 * 	wrapper_class: "custom-style",
	 * 	currency: "USD"
	 * }
	 * case:
	 * - against total amount 120, we could have 140 allocated via an invoice total
	 * - naturally 120 out of the invoice total is allocated, so 20 is unallocated
	 * - in this case, "To Allocate" should be 0 (-20), for transparency
	*/
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		this.$wrapper.empty();
		let $container = null;

		if (this.$wrapper.find(".report-summary").length > 0) {
			$container = this.$wrapper.find(".report-summary");
			$container.empty();
		} else {
			$container = this.$wrapper.append(
				`<div class="report-summary ${this.wrapper_class || ""}"></div>`
			).find(".report-summary");
		}

		Object.keys(this.values).map((key) => {
			let values = this.values[key];
			if (values[2] && values[2] !== values[0]) {
				// handle the case where we have two values to show
				let df = {fieldtype: "Currency", options: "currency"};
				let value_1 = frappe.format(
					values[0], df, { only_value: true }, { currency: this.currency }
				);
				let value_2 = frappe.format(
					values[2], df, { only_value: true }, { currency: this.currency }
				);
				let visible_value = `${value_1} (${value_2})`;
				var number_card = $(
					`<div class="summary-item">
						<div class="summary-label">${__(key)}</div>
						<div class="summary-value">${visible_value}</div>
					</div>`
				);
			} else {
				let data = {
					value: values[0],
					label: __(key),
					datatype: "Currency",
					currency: this.currency,
				};
				var number_card = frappe.utils.build_summary_item(data);
			}

			$container.append(number_card);
			if (values.length > 1) {
				let $text = number_card.find(".summary-value");
				$text.addClass(values[1]);
			}
		});
	}
}