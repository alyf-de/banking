frappe.provide("banking.utils");

banking.utils.create_party_bank_account = function (
	party_type,
	party,
	account_name
) {
	const GERMAN_IBAN_PREFIX = "DE";
	const GERMAN_IBAN_LENGTH = 22;

	return new Promise((resolve, reject) => {
		const dialog = frappe.prompt(
			[
				{
					fieldname: "iban",
					label: __("IBAN"),
					fieldtype: "Data",
					reqd: 1,
					onchange: () => {
						const iban = dialog.get_value("iban");

						if (
							iban?.trim().startsWith(GERMAN_IBAN_PREFIX) &&
							iban?.replaceAll(" ", "").length === GERMAN_IBAN_LENGTH
						) {
							dialog.set_df_property("bank", "hidden", true);
							dialog.set_df_property("bank", "reqd", false);
							dialog.set_value("bank", null);
						} else {
							dialog.set_df_property("bank", "hidden", false);
							dialog.set_df_property("bank", "reqd", true);
						}
					},
				},
				{
					fieldname: "bank",
					label: __("Bank"),
					fieldtype: "Link",
					options: "Bank",
				},
			],
			(values) => {
				frappe
					.xcall("banking.utils.create_party_bank_account", {
						iban: values.iban,
						bank: values.bank,
						party_type: party_type,
						party: party,
						account_name: account_name,
					})
					.then((bank_account) => resolve(bank_account))
					.catch(() => reject());
			}
		);

		dialog.onhide = () => {
			if (!dialog.primary_action_fulfilled) {
				reject();
			}
		};

		dialog.show();
	});
};
