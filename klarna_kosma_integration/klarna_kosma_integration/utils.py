# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import Dict

import frappe
from frappe import _

from erpnext.accounts.doctype.bank.bank import Bank

def add_bank(bank_data: Dict) -> Bank:
	bank, bank_name = None, bank_data.get("bank_name")

	# TODO: get bank name. Demo response has no bank name
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
					"iban": bank_data.get("iban")
				}
			)
			bank.insert()
		except Exception:
			frappe.log_error(title=_("Bank creation failed"), message=frappe.get_traceback())
	else:
		bank = frappe.get_doc("Bank", bank_name)
		bank.update({
			"bank_name": bank_name,
			"swift_number": bank_data.get("bic")
		})
		bank.save()

	return bank

def create_bank_account(account, bank, company, default_gl_account):
	bank_account_name = "{} - {}".format(account.get("name"), bank.get("bank_name"))
	existing_bank_account = frappe.db.exists("Bank Account", bank_account_name)

	if not existing_bank_account:
		try:
			new_account = frappe.get_doc(
				{
					"doctype": "Bank Account",
					"bank": bank.get("bank_name"),
					"account": default_gl_account.account,
					"account_name": account.get("alias"), # TODO: No Name in response. Generate name ?
					# TODO: add custom field for account holder name ?
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
				_("Bank account {0} already exists and could not be created again").format(new_account.name)
			)
		except Exception:
			frappe.log_error(title=_("Bank Account creation has failed"), message=frappe.get_traceback())
			frappe.throw(
				_("There was an error creating Bank Account while linking with Kosma."),
				title=_("Kosma Link Failed"),
			)
	else:
		try:
			existing_account = frappe.get_doc("Bank Account", existing_bank_account)
			existing_account.update(
				{
					"bank": bank.get("bank_name"),
					"account_name": account.get("account_name"),
					"account_type": account.get("account_type", ""),
				}
			)
			existing_account.save()
		except Exception:
			frappe.log_error(title=_("Bank Account update has failed"), message=frappe.get_traceback())
			frappe.throw(
				_("There was an error updating Bank Account {} while linking with Kosma.").format(
					existing_bank_account
				),
				title=_("Kosma Link Failed"),
			)