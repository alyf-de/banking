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
from frappe.utils import formatdate, nowdate

from erpnext.accounts.utils import get_fiscal_year

from klarna_kosma_integration.connectors.klarna_kosma_consent import (
	KlarnaKosmaConsent,
)
from klarna_kosma_integration.connectors.klarna_kosma_flow import (
	KlarnaKosmaFlow,
)
from klarna_kosma_integration.connectors.kosma_transaction import (
	KosmaTransaction,
)

from klarna_kosma_integration.klarna_kosma_integration.utils import (
	add_bank,
	create_bank_account,
	create_bank_transactions,
	create_session_doc,
	get_account_name,
	get_consent_data,
	get_session_flow_ids,
	needs_consent,
	update_account,
	update_bank,
)


class KlarnaKosmaSettings(Document):
	pass


@frappe.whitelist()
def get_client_token(current_flow: str) -> Dict:
	"""
	Returns Client Token to render XS2A App & Short Session ID to track session
	"""
	settings = frappe.get_single("Klarna Kosma Settings")

	flow = KlarnaKosmaFlow(env=settings.env, api_token=settings.get_password("api_token"))

	session_details = flow.start_session()
	session_doc = create_session_doc(session_details)

	flow_data = flow.start(flow_type=current_flow, flows=session_details.get("flows"))

	# Update Flow info in Session Doc
	session_doc.update(
		{
			"flow_id": flow_data.get("flow_id"),
			"flow_state": flow_data.get("state"),
		}
	)
	session_doc.save()

	session_data = {
		"session_id_short": session_details.get("session_id_short"),
		"client_token": flow_data.get("client_token"),
	}
	return session_data


@frappe.whitelist()
def fetch_accounts_and_bank(session_id_short: str = None) -> Dict:
	"""Fetch Accounts via Flow API after XS2A App interaction."""
	session_id, flow_id = get_session_flow_ids(session_id_short)
	settings = frappe.get_single("Klarna Kosma Settings")
	flow = KlarnaKosmaFlow(env=settings.env, api_token=settings.get_password("api_token"))

	accounts_data = flow.accounts(session_id, flow_id)  # Fetch Accounts
	frappe.db.set_value("Klarna Kosma Session", session_id_short, "flow_state", "FINISHED")

	# Get bank from session state
	session = flow.get_session(session_id)
	bank_name = get_session_bank(session)

	accounts_data["result"]["bank_name"] = bank_name

	# Get and store Bank Consent in Bank record
	consent = flow.get_consent(session_id)
	set_consent(consent, bank_name)

	flow.end_session(session_id)
	frappe.db.set_value("Klarna Kosma Session", session_id_short, "status", "Closed")
	frappe.db.commit()

	return accounts_data.get("result", {})


def get_session_bank(session: Dict) -> str:
	"""Get Bank name from session and create Bank record if absent."""
	bank_data = session.get("bank", {})
	bank_name = add_bank(bank_data)
	return bank_name


def set_consent(consent: Dict, bank_name: str) -> None:
	bank_doc = frappe.get_doc("Bank", bank_name)
	bank_doc.update(consent)
	bank_doc.save()


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
		sync_kosma_transactions,
		account=account,
	)

	frappe.msgprint(
		_(
			"Background Transaction Sync is in progress. Please check the Bank Transaction List for updates."
		),
		alert=True,
		indicator="green",
	)


def sync_kosma_transactions(account: str):
	"""Fetch and insert paginated Kosma transactions"""
	start_date = last_sync_date(account)
	account_id, bank = frappe.db.get_value(
		"Bank Account", account, ["kosma_account_id", "bank"]
	)
	consent_id, consent_token = get_consent_data(bank)

	settings = frappe.get_single("Klarna Kosma Settings")
	kosma = KlarnaKosmaConsent(
		env=settings.env, api_token=settings.get_password("api_token")
	)

	next_page, url, offset = True, None, None

	while next_page:
		transactions = kosma.transactions(
			account_id, start_date, consent_id, consent_token, url, offset
		)
		new_consent_token = exchange_consent_token(transactions, bank)

		# Process Request Response
		transaction = KosmaTransaction(transactions)
		next_page = transaction.is_next_page()
		if next_page:
			url, offset = transaction.next_page_request()
			consent_token = new_consent_token

		if transaction.transaction_list:
			create_bank_transactions(account, transaction.transaction_list)


def exchange_consent_token(response: dict, bank: str):
	if (not response) or (not isinstance(response, dict)):
		return

	new_consent_token = response.get("consent_token")
	if new_consent_token:
		bank_doc = frappe.get_doc("Bank", bank)
		bank_doc.consent_token = new_consent_token
		bank_doc.save()
		frappe.db.commit()

	return new_consent_token


def last_sync_date(account_name: str):
	last_sync_date = frappe.db.get_value(
		"Bank Account", account_name, "last_integration_date"
	)
	if last_sync_date:
		return formatdate(last_sync_date, "YYYY-MM-dd")
	else:
		current_fiscal_year = get_fiscal_year(nowdate(), as_dict=True)
		date = current_fiscal_year.year_start_date
		return formatdate(date, "YYYY-MM-dd")


@frappe.whitelist()
def sync_all_accounts_and_transactions():
	"""
	Refresh all Bank accounts and enqueue their transactions sync.
	"""
	banks = frappe.get_all("Bank", filters={"consent_id": ["is", "set"]}, pluck="name")
	settings = frappe.get_single("Klarna Kosma Settings")
	env, api_token = settings.env, settings.get_password("api_token")

	# Update all bank accounts
	accounts_list = []
	for bank in banks:
		consent_id, consent_token = get_consent_data(bank)

		accounts = KlarnaKosmaConsent(env, api_token).accounts(consent_id, consent_token)
		exchange_consent_token(accounts, bank)

		accounts = accounts.get("result", {}).get("accounts")

		for account in accounts:
			account_name = get_account_name(account)
			bank_account_name = "{} - {}".format(account_name, bank)

			if not frappe.db.exists("Bank Account", bank_account_name):
				continue

			update_account(account, bank_account_name)
			accounts_list.append(bank_account_name)  # list of legitimate bank account names

	for bank_account in accounts_list:
		sync_transactions(account=bank_account)
