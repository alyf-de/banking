# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict, List

import frappe
from erpnext.accounts.doctype.bank.bank import Bank
from frappe import _
from frappe.utils import getdate


def get_session_flow_ids(session_id_short: str):
	# TODO: figure out why flow_id is not encrypted
	doc = frappe.get_doc("Klarna Kosma Session", session_id_short)
	session_id = doc.get_password("session_id")

	return session_id, doc.flow_id


def add_bank(bank_data: Dict, bank_name: str = None) -> Bank:
	bank, bank_name = None, bank_data.get("bank_name") or bank_name

	if not bank_name:
		frappe.log_error(title=_("Bank Name missing"), message=json.dumps(bank_data))
		frappe.throw(_("Failed to get Bank Name linked to account"))

	if not frappe.db.exists("Bank", bank_name):
		try:
			bank = frappe.get_doc(
				{
					"doctype": "Bank",
					"bank_name": bank_name,
					"swift_number": bank_data.get("bic"),
					"iban": bank_data.get("iban"),
				}
			)
			bank.insert()
		except Exception:
			frappe.log_error(title=_("Bank creation failed"), message=frappe.get_traceback())
	else:
		bank = frappe.get_doc("Bank", bank_name)
		bank.update({"bank_name": bank_name, "swift_number": bank_data.get("bic")})
		bank.save()

	return bank


def create_bank_account(account, bank, company, default_gl_account):
	account_name = get_account_name(account)
	bank_account_name = "{} - {}".format(account_name, bank.get("bank_name"))
	existing_bank_account = frappe.db.exists("Bank Account", bank_account_name)

	if not existing_bank_account:
		try:
			new_account = frappe.get_doc(
				{
					"doctype": "Bank Account",
					"bank": bank.get("bank_name"),
					"account": default_gl_account.account,
					"account_name": account_name,
					# TODO: add custom field for account holder name ?
					"kosma_account_id": account.get("id"),
					"account_type": account.get("account_type", ""),
					"bank_account_no": account.get("account_number"),
					"iban": account.get("iban"),
					"branch_code": account.get("national_branch_code"),
					"is_company_account": 1,
					"company": company,
				}
			)
			new_account.insert()
		except frappe.UniqueValidationError:
			frappe.msgprint(
				_("Bank account {0} already exists and could not be created again").format(
					new_account.name
				)
			)
		except Exception:
			frappe.log_error(
				title=_("Bank Account creation has failed"), message=frappe.get_traceback()
			)
			frappe.throw(
				_("There was an error creating a Bank Account while linking with Kosma."),
				title=_("Kosma Link Failed"),
			)
	else:
		try:
			existing_account = frappe.get_doc("Bank Account", existing_bank_account)
			existing_account.update(
				{
					"bank": bank.get("bank_name"),
					"account_name": account_name,
					"account_type": account.get("account_type", ""),
					"kosma_account_id": account.get("id"),
				}
			)
			existing_account.save()
		except Exception:
			frappe.log_error(
				title=_("Bank Account update has failed"), message=frappe.get_traceback()
			)
			frappe.throw(
				_("There was an error updating Bank Account {} while linking with Kosma.").format(
					existing_bank_account
				),
				title=_("Kosma Link Failed"),
			)


def get_account_name(account):
	"""
	Generates and returns distinguishable account name.

	Here we can consider alias + holder name to make a distinct account name
	E.g. of Aliases:
	        - Accounts: [{alias: "Girokonto"}, {alias: "Girokonto"}, {alias: "Girokonto"}]
	        - Accounts: [{alias: "My checking account"}, {alias: "My salary account"}, {alias: "My restricted account"}]
	        - (distinct) Accounts: [{alias: "Girokonto (Max Mustermann)"}, {alias: "Girokonto (Hans Mustermann)"}]
	"""
	is_account_alias_distinct = "(" in account.get("alias")
	if is_account_alias_distinct:
		account_name = account.get("alias")
	else:
		account_name = f"{account.get('alias')} ({account.get('holder_name')})"

	return account_name


def create_bank_transactions(account: str, transactions: List[Dict]) -> None:
	last_sync_date = None

	try:
		for transaction in reversed(transactions):
			new_bank_transaction(account, transaction)
			last_sync_date = transaction.get("value_date")

	except Exception:
		frappe.log_error(title=_("Kosma Transaction Error"), message=frappe.get_traceback())
		frappe.throw(_("Error creating transactions"))
	finally:
		if last_sync_date:
			frappe.db.set_value("Bank Account", account, "last_integration_date", last_sync_date)


def new_bank_transaction(account: str, transaction: Dict):
	amount_data = transaction.get("amount", {})
	amount = (
		amount_data.get("amount", 0) / 100
	)  # https://docs.openbanking.klarna.com/xs2a/objects/amount.html

	is_credit = transaction.get("type") == "CREDIT"
	debit = 0 if is_credit else float(amount)
	credit = float(amount) if is_credit else 0

	state_map = {
		"PROCESSED": "Settled",
		"PENDING": "Pending",
		"CANCELED": "Settled",  # TODO: is this status ok ? Should we even consider making cancelled/failed records
		"FAILED": "Settled",
	}
	status = state_map[transaction.get("state")]

	transaction_id = transaction.get("transaction_id")
	if not frappe.db.exists("Bank Transaction", {"transaction_id": transaction_id}):
		new_transaction = frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"date": getdate(transaction.get("value_date")),
				"status": status,
				"bank_account": account,
				"deposit": debit,
				"withdrawal": credit,  # TODO: verify
				"currency": amount_data.get("currency"),
				"transaction_id": transaction_id,
				"reference_number": transaction.get("bank_references", {}).get("end_to_end"),
				"description": transaction.get("reference"),
				"kosma_party_name": transaction.get("counter_party", {}).get("holder_name"),
			}
		)
		new_transaction.insert()
		new_transaction.submit()
