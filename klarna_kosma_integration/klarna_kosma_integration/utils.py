# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict

import frappe
from erpnext.accounts.doctype.bank.bank import Bank
from frappe import _


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
