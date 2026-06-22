# Copyright (c) 2025, ALYF GmbH and Contributors
# See license.txt

import frappe
from erpnext.accounts.doctype.account.test_account import create_account


def set_automatic_bank_fee_entries(enabled: bool) -> None:
	frappe.db.set_single_value(
		"Banking Settings",
		"enable_automatic_journal_entries_for_bank_fees",
		int(enabled),
	)


def get_bank_parent_account(company: str = "_Test Company") -> str:
	return frappe.db.get_value("Account", {"account_type": "Bank", "is_group": 1, "company": company})


def create_currency_account(
	currency: str, parent_account: str, account_name: str, company: str = "_Test Company"
):
	account = create_account(
		account_name=account_name,
		account_type="Bank",
		parent_account=parent_account,
		company=company,
		account_currency=currency,
	)
	return frappe.get_doc("Account", account)


def create_bank_account(
	account: str,
	account_name: str = "_Test_B_Account",
	*,
	bank_fee_account: str | None = None,
	company: str = "_Test Company",
	bank: str = "_Test_Bank",
):
	bank_account = frappe.new_doc("Bank Account")
	bank_account.account_name = account_name
	bank_account.account = account
	bank_account.bank = bank
	bank_account.company = company
	bank_account.is_company_account = 1
	if bank_fee_account:
		bank_account.bank_fee_account = bank_fee_account
	bank_account.insert(ignore_permissions=True, ignore_links=True)
	return bank_account


def make_bank_transaction(
	*,
	company: str | None = "_Test Company",
	run_before_validate: bool = False,
	**values,
):
	doc = frappe.new_doc("Bank Transaction")
	if company is not None:
		doc.company = company
	doc.update(values)
	if run_before_validate:
		doc.run_method("before_validate")
	return doc


def create_bank_transaction(
	*,
	company: str = "_Test Company",
	run_before_validate: bool = False,
	**values,
):
	doc = make_bank_transaction(
		company=company,
		run_before_validate=run_before_validate,
		**values,
	)
	doc.insert(ignore_permissions=True, ignore_mandatory=True, ignore_links=True)
	return doc
