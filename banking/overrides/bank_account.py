import frappe
from frappe import _
from frappe.utils import cint

from banking.ebics.utils import register_fintech


def before_validate(doc, method):
	"""Remove spaces from IBAN"""
	if doc.iban:
		doc.iban = doc.iban.replace(" ", "")


def validate(doc, method):
	validate_account_currencies(doc)
	validate_required_bank_fee_account(doc)
	validate_default_mode_of_payment(doc)
	validate_bank_bic(doc)


def validate_account_currencies(doc):
	if doc.account and doc.bank_fee_account:
		bank_account_currency = frappe.db.get_value("Account", doc.account, "account_currency")
		bank_fee_currency = frappe.db.get_value("Account", doc.bank_fee_account, "account_currency")
		if bank_account_currency != bank_fee_currency:
			frappe.throw(_("Company Account and Bank Fee Account must be in the same currency!"))


def validate_default_mode_of_payment(doc):
	"""The Default Mode of Payment must book to this account, like the field's query in the form."""
	if not (doc.default_mode_of_payment and doc.is_company_account and doc.account):
		return

	books_to_account = frappe.db.exists(
		"Mode of Payment Account",
		{"parent": doc.default_mode_of_payment, "company": doc.company, "default_account": doc.account},
	)
	if not books_to_account:
		frappe.throw(
			_("Default Mode of Payment {0} does not book to account {1}.").format(
				frappe.bold(doc.default_mode_of_payment), frappe.bold(doc.account)
			)
		)


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


def validate_bank_bic(doc):
	"""The BIC of the linked Bank must belong to the IBAN. fintech knows the bank codes of DE, AT and CH."""
	if not (doc.iban and doc.iban[:2] in ("DE", "AT", "CH") and doc.bank):
		return

	bank_bic = frappe.db.get_value("Bank", doc.bank, "swift_number")
	if not bank_bic:
		return

	register_fintech()
	from fintech import iban

	try:
		iban_bic = iban.get_bic(doc.iban)
	except ValueError:
		return  # unknown bank code, nothing to compare

	# "XXX" is the default branch code, so "ABCDEFGH" equals "ABCDEFGHXXX"
	if bank_bic.ljust(11, "X") != iban_bic.ljust(11, "X"):
		frappe.throw(
			_(
				"Bank {0} has the BIC {1}, but IBAN {2} belongs to the BIC {3}. Please select a Bank with the BIC {3}."
			).format(frappe.bold(doc.bank), bank_bic, doc.iban, frappe.bold(iban_bic))
		)
