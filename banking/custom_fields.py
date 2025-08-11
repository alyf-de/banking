from banking.utils import identity as _


def get_custom_fields():
	return {
		"Bank": [
			dict(
				fieldname="ebics_section",
				label=_("EBICS"),
				fieldtype="Section Break",
				insert_after="plaid_access_token",
			),
			dict(
				fieldname="ebics_host_id",
				label=_("EBICS Host ID"),
				fieldtype="Data",
				insert_after="ebics_section",
				translatable=0,
			),
			dict(
				fieldname="ebics_url",
				label=_("EBICS URL"),
				fieldtype="Data",
				options="URL",
				insert_after="ebics_host_id",
				translatable=0,
			),
		],
		"Purchase Invoice": [
			dict(
				fieldname="banking_section",
				label=_("Banking"),
				fieldtype="Section Break",
				insert_after="payments_tab",
			),
			dict(
				fieldname="supplier_bank_account",
				label=_("Supplier Bank Account"),
				fieldtype="Link",
				options="Bank Account",
				insert_after="banking_section",
			),
		],
	}
