import frappe
from frappe import _
from frappe.utils import cint


def before_validate(doc, method):
	"""Remove spaces from IBAN"""
	if doc.iban:
		doc.iban = doc.iban.replace(" ", "")


def validate(doc, method):
	validate_account_currencies(doc)
	validate_required_bank_fee_account(doc)


def validate_account_currencies(doc):
	if doc.account and doc.bank_fee_account:
		bank_account_currency = frappe.db.get_value("Account", doc.account, "account_currency")
		bank_fee_currency = frappe.db.get_value("Account", doc.bank_fee_account, "account_currency")
		if bank_account_currency != bank_fee_currency:
			frappe.throw(_("Company Account and Bank Fee Account must be in the same currency!"))


def validate_required_bank_fee_account(doc):
	if doc.bank_fee_account or not cint(doc.is_company_account) or not automatic_fee_entries_enabled():
		return

	frappe.throw(
		_(
			"Bank Fee Account is mandatory for company Bank Accounts while automatic journal entries for bank fees are enabled in Banking Settings."
		)
	)


def automatic_fee_entries_enabled() -> bool:
	return bool(
		cint(frappe.db.get_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees"))
	)


def get_company_bank_accounts_without_fee_account() -> list[str]:
	return frappe.get_all(
		"Bank Account",
		filters={"is_company_account": 1, "bank_fee_account": ["is", "not set"]},
		pluck="name",
	)
