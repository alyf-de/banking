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
from klarna_kosma_integration.klarna_kosma_integration.utils import (
	add_bank,
	create_bank_account,
)


class KlarnaKosmaSettings(Document):
	pass


@frappe.whitelist()
def get_client_token():
	kosma = KlarnaKosmaConnector()
	return kosma.get_client_token()


@frappe.whitelist()
def fetch_flow_data(session_id, flow_id):
	kosma = KlarnaKosmaConnector()
	flow_data = kosma.execute_flow(session_id, flow_id)
	return flow_data


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
