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

from klarna_kosma_integration.connectors.klarna_kosma_flow import (
	KlarnaKosmaFlow,
)

from klarna_kosma_integration.klarna_kosma_integration.utils import (
	create_bank_account,
	needs_consent,
	update_bank,
)


class KlarnaKosmaSettings(Document):
	pass


@frappe.whitelist()
def get_client_token(current_flow: str):
	"""
	Returns Client Token to render XS2A App & Short Session ID to track session
	"""
	settings = frappe.get_single("Klarna Kosma Settings")
	config = dict(env=settings.env, api_token=settings.get_password("api_token"))

	flow = KlarnaKosmaFlow(config)
	session_details = flow.start_session()
	# Update Flow info in Session Doc
	# session_doc = frappe.get_doc("Klarna Kosma Session", session_id_short)
	# session_doc.update(
	# 	{
	# 		"flow_id": flow_response_data.get("flow_id"),
	# 		"flow_state": flow_response_data.get("state"),
	# 	}
	# )
	# session_doc.save()

	flow_data = flow.start(flow_type=current_flow, flows=session_details.get("flows"))
	# update flow id and flow state

	session_data = {
		"session_id_short": session_details.get("session_id_short"),
		"client_token": flow_data.get("client_token"),
	}
	return session_data


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

	frappe.enqueue(
		"klarna_kosma_integration.connectors.klarna_kosma_consent.sync_transactions",
		account=account,
	)

	frappe.msgprint(
		_(
			"Transaction Sync is in progress in the background. Please check the Bank Transaction List for updates."
		),
		alert=True,
		indicator="green",
	)
