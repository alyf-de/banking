import frappe
from frappe import _

from banking.ebics.manager import EBICSManager


def get_ebics_manager(ebics_user: str) -> "EBICSManager":
	"""Get an EBICSManager instance for the given EBICS User.

	:param ebics_user: The name of the EBICS User record.
	"""
	banking_settings = frappe.get_single("Banking Settings")
	banking_settings.ensure_ebics_keyring_passphrase()

	manager = EBICSManager(
		license_name=banking_settings.fintech_licensee_name,
		license_key=banking_settings.get_password("fintech_license_key"),
	)

	manager.set_keyring(
		frappe.get_site_path("ebics_keyring.json"),
		banking_settings.get_password("ebics_keyring_passphrase"),
	)

	bank, partner_id, user_id = frappe.db.get_value(
		"EBICS User", ebics_user, ["bank", "partner_id", "user_id"]
	)
	host_id, url = frappe.db.get_value("Bank", bank, ["ebics_host_id", "ebics_url"])

	manager.set_user(partner_id, user_id)
	manager.set_bank(host_id, url)

	return manager


def sync_ebics_transactions(ebics_user: str, start_date: str, end_date: str):
	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	manager = get_ebics_manager(ebics_user)
	for camt_document in manager.download_bank_statements(start_date, end_date):
		bank_account = frappe.db.get_value(
			"Bank Account",
			{
				"iban": camt_document.iban,
				"disabled": 0,
				"bank": user.bank,
				"is_company_account": 1,
				"company": user.company,
			},
		)
		if not bank_account:
			frappe.throw(
				_("Bank Account not found for IBAN {0}").format(camt_document.iban)
			)

		for transaction in camt_document:
			if transaction.status != "BOOK":
				# Skip PDNG and INFO transactions
				continue

			if transaction.batch and len(transaction):
				# Split batch transactions into sub-transactions, based on info
				# from camt.054 that is sometimes available.
				# If that's not possible, create a single transaction
				for sub_transaction in transaction:
					_create_bank_transaction(
						bank_account, user.company, sub_transaction
					)
			else:
				_create_bank_transaction(bank_account, user.company, transaction)


def _create_bank_transaction(bank_account: str, company: str, sepa_transaction):
	"""Create an ERPNext Bank Transaction from a given fintech.sepa.SEPATransaction."""
	# sepa_transaction.bank_reference can be None, but we can still find an ID in the XML
	alternative_id = (
		sepa_transaction._xmlobj.to_dict()
		.get("TxDtls", {})
		.get("Refs", {})
		.get("TxId", None)
	)
	transaction_id = sepa_transaction.bank_reference or alternative_id

	# NOTE: This does not work for old data, this ID is different from Kosma's
	if sepa_transaction.bank_reference and frappe.db.exists(
		"Bank Transaction",
		{"transaction_id": transaction_id, "bank_account": bank_account},
	):
		return

	bt = frappe.new_doc("Bank Transaction")
	bt.date = sepa_transaction.date
	bt.bank_account = bank_account
	bt.company = company

	amount = float(sepa_transaction.amount.value)
	bt.deposit = max(amount, 0)
	bt.withdrawal = abs(min(amount, 0))
	bt.currency = sepa_transaction.amount.currency

	bt.description = "\n".join(sepa_transaction.purpose)
	bt.reference_number = sepa_transaction.eref
	bt.transaction_id = transaction_id
	bt.bank_party_iban = sepa_transaction.iban
	bt.bank_party_name = sepa_transaction.name

	with contextlib.suppress(frappe.exceptions.UniqueValidationError):
		bt.insert()
		bt.submit()
