import contextlib
from typing import TYPE_CHECKING

import frappe
from frappe import _

from banking.ebics.manager import EBICSManager

if TYPE_CHECKING:
	from datetime import date
	from .types import SEPATransaction
	from banking.ebics.doctype.ebics_user.ebics_user import EBICSUser


def get_ebics_manager(
	ebics_user: "EBICSUser",
	passphrase: str | None = None,
	sig_passphrase: str | None = None,
) -> "EBICSManager":
	"""Get an EBICSManager instance for the given EBICS User.

	:param ebics_user: The EBICS User record.
	:param passphrase: The secret passphrase for uploads to the bank.
	"""
	banking_settings = frappe.get_single("Banking Settings")

	manager = EBICSManager(
		license_name=banking_settings.fintech_licensee_name,
		license_key=banking_settings.get_password("fintech_license_key"),
	)

	manager.set_keyring(
		keys=ebics_user.get_keyring(),
		save_to_db=ebics_user.store_keyring,
		sig_passphrase=sig_passphrase,
		passphrase=passphrase or ebics_user.get_password("passphrase"),
	)

	manager.set_user(ebics_user.partner_id, ebics_user.user_id)

	host_id, url = frappe.db.get_value(
		"Bank", ebics_user.bank, ["ebics_host_id", "ebics_url"]
	)
	manager.set_bank(host_id, url)

	return manager


def sync_ebics_transactions(
	ebics_user: str,
	start_date: str | None = None,
	end_date: str | None = None,
	passphrase: str | None = None,
	intraday: bool = False,
):
	user = frappe.get_doc("EBICS User", ebics_user)
	manager = get_ebics_manager(ebics_user=user, passphrase=passphrase)

	# Not sure yet, how reliable permitted types are. For now, we just log an error
	# instead of raising an exception or returning.
	permitted_types = manager.get_permitted_order_types()
	if intraday and "C52" not in permitted_types:
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"It seems like EBICS User {0} lacks permission 'C52' for downloading intraday transactions. The permitted types are: {1}."
			).format(ebics_user, ", ".join(permitted_types)),
		)

	if not intraday and "C53" not in permitted_types:
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"It seems like EBICS User {0} lacks permission 'C52' for downloading booked bank statements. The permitted types are: {1}."
			).format(ebics_user, ", ".join(permitted_types)),
		)

	for camt_document in (
		manager.download_intraday_transactions()
		if intraday
		else manager.download_bank_statements(start_date, end_date)
	):
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
			frappe.log_error(
				title=_("Banking Error"),
				message=_("Bank Account not found for IBAN {0}").format(camt_document.iban),
			)
			continue

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
						bank_account, user.company, sub_transaction, user.start_date
					)
			else:
				_create_bank_transaction(bank_account, user.company, transaction, user.start_date)


def _create_bank_transaction(
	bank_account: str,
	company: str,
	sepa_transaction: "SEPATransaction",
	start_date: "date" = None,
):
	"""Create an ERPNext Bank Transaction from a given fintech.sepa.SEPATransaction.

	https://www.joonis.de/en/fintech/doc/sepa/#fintech.sepa.SEPATransaction
	"""
	# sepa_transaction.bank_reference can be None, but we can still find an ID in the XML
	# For our test bank, the latter is a timestamp with nanosecond accuracy.
	transaction_id = (
		sepa_transaction.bank_reference or sepa_transaction._xmlobj.Refs.TxId.text
	)

	# NOTE: This does not work for old data, this ID is different from Kosma's
	if transaction_id and frappe.db.exists(
		"Bank Transaction",
		{"transaction_id": transaction_id, "bank_account": bank_account},
	):
		return

	if start_date and sepa_transaction.date < start_date:
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
