from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
from frappe.utils import now_datetime

if TYPE_CHECKING:
	from erpnext.accounts.doctype.bank.bank import Bank
	from erpnext.accounts.doctype.bank_account.bank_account import BankAccount


def before_tests():
	# complete setup if missing
	year = now_datetime().year
	if not frappe.get_list("Company"):
		setup_complete(
			{
				"currency": "EUR",
				"full_name": "Test User",
				"company_name": "Bolt Trades",
				"timezone": "Europe/Berlin",
				"company_abbr": "BT",
				"industry": "Manufacturing",
				"country": "Germany",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@erpnext.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)

	frappe.db.commit()  # nosemgrep


def identity(x):
	"""For dummy translations."""
	return x


@frappe.whitelist(methods=["POST"])
def create_party_bank_account(
	party_type: str, party: str, iban: str, account_name: str | None = None, bank: str | None = None
) -> str:
	_iban = iban.replace(" ", "").upper()

	existing_bank_account = frappe.db.exists("Bank Account", {"iban": _iban})
	if existing_bank_account:
		return existing_bank_account

	if not bank:
		if _iban.startswith("DE"):
			bank = create_bank(_iban)
		else:
			frappe.throw(_("For non-German IBANs, a Bank must be provided."))

	if not account_name:
		party_doc = frappe.get_doc(party_type, party)
		account_name = party_doc.get_title()

	doc: BankAccount = frappe.new_doc("Bank Account")
	doc.iban = _iban
	doc.bank = bank
	doc.party_type = party_type
	doc.party = party
	doc.account_name = account_name
	doc.save()

	return doc.name


def create_bank(iban: str) -> str:
	import kontocheck

	kontocheck.lut_load()

	bank_name = kontocheck.get_bankname(iban)
	swift_number = kontocheck.get_bic(iban)

	existing_bank = frappe.db.exists("Bank", {"swift_number": swift_number})
	if existing_bank:
		return existing_bank

	doc: Bank = frappe.new_doc("Bank")
	doc.bank_name = bank_name
	doc.swift_number = swift_number
	doc.insert()

	return doc.name
