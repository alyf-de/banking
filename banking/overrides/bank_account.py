import frappe
from frappe import _


def before_validate(doc, method):
	"""Remove spaces from IBAN"""
	if doc.iban:
		doc.iban = doc.iban.replace(" ", "")


def validate(doc, method):
	validate_account_currencies(doc)


def validate_account_currencies(doc):
	if doc.account and doc.bank_fee_account:
		bank_account_currency = frappe.db.get_value("Account", doc.account, "account_currency")
		bank_fee_currency = frappe.db.get_value("Account", doc.bank_fee_account, "account_currency")
		if bank_account_currency != bank_fee_currency:
			frappe.throw(_("Company Account and Bank Fee Account must be in the same currency!"))
