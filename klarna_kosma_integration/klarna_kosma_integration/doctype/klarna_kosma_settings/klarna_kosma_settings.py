# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict

import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)
from frappe import _
from frappe.model.document import Document

from klarna_kosma_integration.klarna_kosma_integration.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from klarna_kosma_integration.klarna_kosma_integration.klarna_kosma_flow import (
	KlarnaKosmaFlow,
)
from klarna_kosma_integration.klarna_kosma_integration.utils import (
	create_bank_account,
	update_bank,
)


class KlarnaKosmaSettings(Document):
	pass


@frappe.whitelist()
def get_client_token(current_flow: str):
	kosma = KlarnaKosmaFlow()
	return kosma.get_client_token(current_flow)


@frappe.whitelist()
def fetch_accounts(session_id_short: str = None) -> Dict:
	kosma = KlarnaKosmaFlow()
	accounts_data = kosma.fetch_accounts(session_id_short)

	return accounts_data.get("data", {}).get("result", {})


@frappe.whitelist()
def add_bank_accounts(accounts: str, company: str, bank_name: str) -> None:
	accounts = json.loads(accounts)
	accounts = accounts.get("accounts")

	default_gl_account = get_default_bank_cash_account(company, "Bank")
	if not default_gl_account:
		frappe.throw(_("Please setup a default bank account for company {0}").format(company))

	for account in accounts:
		update_bank(account, bank_name)

		if not frappe.db.exists("Bank Account Type", account.get("account_type")):
			frappe.get_doc(
				{"doctype": "Bank Account Type", "account_type": account.get("account_type")}
			).insert()

		create_bank_account(account, bank_name, company, default_gl_account)


@frappe.whitelist()
def sync_transactions(account: str) -> None:
	bank = frappe.db.get_value("Bank Account", account, "bank")

	if needs_consent(bank):  # UX
		error_msg = _("The Consent Token has expired/is unavailable for Bank {0}.").format(
			frappe.bold(bank)
		)
		action_msg = _(" Please click on the {0} button").format(
			frappe.bold("Sync Bank and Accounts")
		)
		frappe.throw(
			msg=error_msg + action_msg,
			title=_("Kosma Error"),
		)

	# TODO: remove now=True
	frappe.enqueue(
		"klarna_kosma_integration.klarna_kosma_integration.klarna_kosma_consent.sync_transactions",
		account=account,
		now=True,
	)

	frappe.msgprint(
		_("Transaction Sync is in progress in the background."), alert=True, indicator="green"
	)


@frappe.whitelist()
def needs_consent(bank: str) -> bool:
	kosma = KlarnaKosmaConnector()
	return kosma.needs_consent(bank)


@frappe.whitelist()
def clear_consent():
	frappe.db.set_value(
		"Klarna Kosma Settings",
		None,
		{
			"consent_token": None,
			"consent_id": None,
			"consent_expiry": None,
		},
	)
