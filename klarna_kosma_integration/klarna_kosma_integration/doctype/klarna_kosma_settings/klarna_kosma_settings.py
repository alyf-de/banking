# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json

import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)
from frappe import _
from frappe.model.document import Document

from klarna_kosma_integration.klarna_kosma_integration.doctype.klarna_kosma_settings.klarna_kosma_connector import (
	KlarnaKosmaConnector,
)
from klarna_kosma_integration.klarna_kosma_integration.doctype.klarna_kosma_settings.klarna_kosma_consent import (
	KlarnaKosmaConsent,
)
from klarna_kosma_integration.klarna_kosma_integration.doctype.klarna_kosma_settings.klarna_kosma_flow import (
	KlarnaKosmaFlow,
)
from klarna_kosma_integration.klarna_kosma_integration.utils import (
	add_bank,
	create_bank_account,
)


class KlarnaKosmaSettings(Document):
	pass


@frappe.whitelist()
def get_client_token():
	kosma = KlarnaKosmaFlow()
	return kosma.get_client_token()


@frappe.whitelist()
def fetch_accounts(api_type: str, session_id: str = None, flow_id: str = None):
	if api_type == "flow":
		kosma = KlarnaKosmaFlow()
		accounts_data = kosma.fetch_accounts(session_id, flow_id)
	else:
		kosma = KlarnaKosmaConsent()
		accounts_data = kosma.fetch_accounts()

	return accounts_data


@frappe.whitelist()
def add_bank_and_accounts(accounts, company, bank_name=None):
	accounts = json.loads(accounts)
	accounts = accounts.get("data").get("result").get("accounts")

	default_gl_account = get_default_bank_cash_account(company, "Bank")
	if not default_gl_account:
		frappe.throw(_("Please setup a default bank account for company {0}").format(company))

	for account in accounts:
		bank = add_bank(account, bank_name)

		if not frappe.db.exists("Bank Account Type", account.get("account_type")):
			frappe.get_doc(
				{"doctype": "Bank Account Type", "account_type": account.get("account_type")}
			).insert()

		create_bank_account(account, bank, company, default_gl_account)


@frappe.whitelist()
def fetch_transactions(api_type: str, session_id: str = None, flow_id: str = None):
	if api_type == "flow":
		kosma = KlarnaKosmaFlow()
		transactions_data = kosma.fetch_transactions(session_id, flow_id)
	else:
		kosma = KlarnaKosmaConsent()
		transactions_data = kosma.fetch_transactions()

	return transactions_data


@frappe.whitelist()
def needs_consent():
	kosma = KlarnaKosmaConnector()
	return kosma.consent_needed
