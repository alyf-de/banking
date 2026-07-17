// Copyright (c) 2026, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.provide("banking.bank_reconciliation");

const CANDIDATE_FIELDS = [
	"deposit",
	"withdrawal",
	"currency",
	"description",
	"reference_number",
	"included_fee",
	"excluded_fee",
	"subtransaction_id",
	"transaction_type",
	"party_type",
	"party",
	"bank_party_name",
	"bank_party_account_number",
	"bank_party_iban",
];

function field_has_value(df, value) {
	if (value === undefined || value === null) {
		return false;
	}
	const ft = df.fieldtype;
	if (frappe.model.numeric_fieldtypes.includes(ft)) {
		return flt(value) !== 0;
	}
	if (ft === "Link" || ft === "Dynamic Link") {
		return Boolean(String(value).trim());
	}
	return String(value).trim() !== "";
}

function get_visible_field_rows(doc) {
	const rows = [];
	for (const fieldname of CANDIDATE_FIELDS) {
		const df = frappe.meta.get_docfield("Bank Transaction", fieldname);
		if (!df) {
			continue;
		}
		const value = doc[fieldname];
		if (!field_has_value(df, value)) {
			continue;
		}
		rows.push({ fieldname, df, value });
	}
	return rows;
}

function format_cell(df, value, doc) {
	const formatted = frappe.format(value, df, { only_value: true }, doc);
	return frappe.utils.escape_html(String(formatted ?? ""));
}

banking.bank_reconciliation.show_rule_creation_dialog = function (doc) {
	if (!doc.bank_account) {
		frappe.throw(__("Set a Bank Account first."));
	}
	if (!frappe.model.can_create("Bank Reconciliation Rule")) {
		frappe.throw(
			__("You do not have permission to create a Bank Reconciliation Rule.")
		);
	}

	const field_rows = get_visible_field_rows(doc);
	if (!field_rows.length) {
		frappe.msgprint(
			__("No filterable field values are set on this Bank Transaction.")
		);
		return;
	}

	const table_rows = field_rows
		.map((row) => {
			const label = frappe.utils.escape_html(__(row.df.label) || row.fieldname);
			const display = format_cell(row.df, row.value, doc);
			return `<tr class="rule-creation-filter-row">
				<td class="text-center" style="width:3rem;">
					<input type="checkbox" class="rule-creation-filter-cb" data-fieldname="${frappe.utils.escape_html(
						row.fieldname
					)}" checked />
				</td>
				<td>${label}</td>
				<td>${display}</td>
			</tr>`;
		})
		.join("");

	const html = `<div style="max-height:22rem; overflow:auto;">
		<table class="table table-bordered table-condensed mb-0">
			<thead>
				<tr>
					<th class="text-center">${frappe.utils.escape_html(__("Use"))}</th>
					<th>${frappe.utils.escape_html(__("Field"))}</th>
					<th>${frappe.utils.escape_html(__("Value"))}</th>
				</tr>
			</thead>
			<tbody>${table_rows}</tbody>
		</table>
	</div>`;

	const dialog = new frappe.ui.Dialog({
		title: __("Create Bank Reconciliation Rule"),
		fields: [{ fieldname: "picker_html", fieldtype: "HTML", label: "" }],
		primary_action_label: __("Create Rule"),
		primary_action: () => {
			const selected = [];
			dialog.$wrapper
				.find(".rule-creation-filter-cb:checked")
				.each(function () {
					const fieldname = $(this).attr("data-fieldname");
					if (fieldname) {
						selected.push(["Bank Transaction", fieldname, "=", doc[fieldname]]);
					}
				});
			if (!selected.length) {
				frappe.msgprint(__("Select at least one field to use as a filter."));
				return;
			}
			dialog.hide();
			frappe.route_options = {
				bank_account: doc.bank_account,
				filters: JSON.stringify(selected),
			};
			frappe.set_route("Form", "Bank Reconciliation Rule", "new");
		},
	});

	dialog.fields_dict.picker_html.$wrapper.html(html);
	dialog.show();
};
