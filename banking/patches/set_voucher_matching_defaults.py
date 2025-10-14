import frappe


def execute():
	"""Fill the new field _Voucher Matching Defaults_ in **Banking Settings** with the previously hardcoded defaults."""
	banking_settings = frappe.get_single("Banking Settings")
	if not banking_settings.voucher_matching_defaults:
		banking_settings.extend(
			"voucher_matching_defaults",
			[
				{
					"document_type": "Sales Invoice",
				},
				{
					"document_type": "Purchase Invoice",
				},
			],
		)
		banking_settings.save()
