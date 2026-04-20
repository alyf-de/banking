import json

import frappe


def execute():
	"""Drop the deprecated 5th element (legacy `hidden` UI flag) from saved
	**Bank Reconciliation Rule** filters.

	Older Frappe versions appended a per-filter `hidden` boolean when the JS
	`FilterGroup` serialized filters back to the form. The flag was UI-only and
	is rejected by Frappe v16's query layer (deprecation warning, removal in a
	future version). The filters here are evaluated server-side via
	`evaluate_filters`, so dropping the trailing element is purely cosmetic.
	"""
	rule = frappe.qb.DocType("Bank Reconciliation Rule")
	rows = (
		frappe.qb.from_(rule)
		.select(rule.name, rule.filters)
		.where(rule.filters.isnotnull())
		.where(rule.filters != "")
		.run(as_dict=True)
	)

	for row in rows:
		try:
			filters = json.loads(row.filters)
		except TypeError, ValueError:
			continue

		changed = False
		for i, f in enumerate(filters):
			if isinstance(f, list) and len(f) == 5:
				filters[i] = f[:4]
				changed = True

		if changed:
			frappe.db.set_value(
				"Bank Reconciliation Rule",
				row.name,
				"filters",
				json.dumps(filters),
				update_modified=False,
			)
