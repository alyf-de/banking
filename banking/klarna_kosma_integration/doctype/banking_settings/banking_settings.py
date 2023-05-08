# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict, Optional, Union

import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)
from frappe import _
from frappe.model.document import Document

from banking.klarna_kosma_integration.admin import Admin
from banking.klarna_kosma_integration.utils import (
	create_bank_account,
	get_account_name,
	needs_consent,
	update_account,
	update_bank,
)


class BankingSettings(Document):
	pass


@frappe.whitelist()
def get_client_token(
	current_flow: str,
	account: Optional[str] = None,
	from_date: Optional[str] = None,
	to_date: Optional[str] = None,
) -> Dict:
	"""
	Returns Client Token to render XS2A App & Short Session ID to track session
	"""
	return Admin().get_client_token(current_flow, account, from_date, to_date)


@frappe.whitelist()
def fetch_accounts_and_bank(session_id_short: str = None, company: str = None) -> Dict:
	"""
	Fetch Accounts via Flow API after XS2A App interaction.
	"""
	return Admin().flow_accounts(session_id_short, company)


@frappe.whitelist()
def add_bank_accounts(accounts: Union[str, list], company: str, bank_name: str) -> None:
	if isinstance(accounts, str):
		accounts = json.loads(accounts)

	default_gl_account = get_default_bank_cash_account(company, "Bank")
	if not default_gl_account:
		frappe.throw(_("Please setup a default bank account for company {0}").format(company))

	for account in accounts:
		update_bank(account, bank_name)

		if not frappe.db.exists("Bank Account Type", account.get("account_type")):
			frappe.get_doc(
				{
					"doctype": "Bank Account Type",
					"account_type": account.get("account_type"),
				}
			).insert()

		create_bank_account(account, bank_name, company, default_gl_account)


@frappe.whitelist()
def sync_transactions(account: str, session_id_short: Optional[str] = None) -> None:
	"""
	Enqueue transactions sync via the Consent API.
	"""
	bank, company = frappe.db.get_value("Bank Account", account, ["bank", "company"])

	if not session_id_short and needs_consent(bank, company):  # UX
		frappe.throw(
			msg=_(
				"The Consent Token has expired/is unavailable for Bank {0}. Please click on the {1} button"
			).format(frappe.bold(bank), frappe.bold(_("Sync Bank and Accounts"))),
			title=_("Kosma Error"),
		)

	frappe.enqueue(
		"banking.klarna_kosma_integration.admin.sync_kosma_transactions",
		account=account,
		session_id_short=session_id_short,
	)

	frappe.msgprint(
		_(
			"Background Transaction Sync is in progress. Please check the Bank Transaction List for updates."
		),
		alert=True,
		indicator="green",
	)


@frappe.whitelist()
def sync_all_accounts_and_transactions():
	"""
	Refresh all Bank accounts and enqueue their transactions sync, via the Consent API.
	Called via hooks.
	"""
	if not frappe.db.get_single_value("Banking Settings", "enabled"):
		return

	accounts_list = []
	bank_consents = frappe.get_all("Bank Consent", fields=["bank", "company"])

	# Update all bank accounts
	for entry in bank_consents:
		accounts = Admin().consent_accounts(entry.get("bank"), entry.get("company"))

		for account in accounts:
			account_name = get_account_name(account)
			bank_account_name = "{} - {}".format(account_name, entry.get("bank"))

			if not frappe.db.exists("Bank Account", bank_account_name):
				continue

			update_account(account, bank_account_name) # update account kosma id

			# list of legitimate bank account names
			accounts_list.append(bank_account_name)

	for bank_account in accounts_list:
		sync_transactions(account=bank_account)
