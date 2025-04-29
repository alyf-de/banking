import contextlib
import json
from typing import TYPE_CHECKING, Literal

import fintech
import frappe
from frappe import _
from frappe.utils.data import get_link_to_form

from banking.ebics.manager import EBICSManager

if TYPE_CHECKING:
	from datetime import date

	from fintech.sepa import SEPATransaction

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
	register_fintech(needs_license_key=True)

	manager = EBICSManager()
	manager.set_keyring(
		keys=ebics_user.get_keyring(),
		save_to_db=ebics_user.store_keyring,
		sig_passphrase=sig_passphrase,
		passphrase=passphrase or ebics_user.get_password("passphrase"),
	)

	manager.set_user(ebics_user.partner_id, ebics_user.user_id)

	host_id, url = frappe.db.get_value("Bank", ebics_user.bank, ["ebics_host_id", "ebics_url"])
	manager.set_bank(host_id, url)

	return manager


def sync_ebics_transactions(
	ebics_user: str,
	requested_by: Literal["User", "System"],
	start_date: str | None = None,
	end_date: str | None = None,
	passphrase: str | None = None,
	intraday: bool = False,
):
	user = frappe.get_doc("EBICS User", ebics_user)
	manager = get_ebics_manager(ebics_user=user, passphrase=passphrase)

	# import possible only after manager is initialized
	from fintech.sepa import (
		CAMTDocument,
	)

	permitted_types = manager.get_permitted_order_types()
	validate_permitted_types(user, permitted_types, intraday)

	with_c54 = user.split_batch_transactions and "C54" in permitted_types
	request = log_request(
		ebics_user,
		"C52" if intraday else "C53",
		requested_by,
		{
			"start_date": start_date,
			"end_date": end_date,
		},
	)

	try:
		client = manager.get_client()
		main_xml = client.C52(start_date, end_date) if intraday else client.C53(start_date, end_date)
		batch_xml = client.C54(start_date, end_date) if with_c54 else None
		request.db_set(
			{
				"status": "Successful",
				"response": json.dumps(
					{file_name: file.decode() for file_name, file in main_xml.items()},
					indent=2,
				),
			}
		)
	except fintech.ebics.EbicsNoDataAvailable:
		request.db_set({"status": "Successful", "response": "No Data Available"})
		return
	except Exception as e:
		request.db_set({"status": "Failed", "response": str(e)})
		frappe.log_error(
			title=_("Banking Error"),
			reference_doctype="EBICS User",
			reference_name=ebics_user,
		)
		return

	# Keep the request log, no matter what happens next.
	frappe.db.commit()

	# We want to process either all documents or none. If we fail to process one, we
	# want to rollback the entire transaction and report an error.
	try:
		for name in sorted(main_xml):
			camt_document = CAMTDocument(xml=main_xml[name], camt54=batch_xml)
			bank_account = get_bank_account(camt_document.iban, user.bank, user.company)
			if not bank_account:
				frappe.log_error(
					title=_("Banking Error"),
					message=_("Bank Account not found for IBAN {0}").format(camt_document.iban),
					reference_doctype="EBICS User",
					reference_name=user.name,
				)
				continue

			process_camt_document(
				camt_document,
				bank_account,
				user.company,
				user.start_date,
				user.split_batch_transactions,
			)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title=_("Banking Error"),
			reference_doctype="EBICS Request",
			reference_name=request.name,
		)
		client.confirm_download(success=False)
		return

	client.confirm_download(success=True)


def validate_permitted_types(user, permitted_types, intraday: bool):
	# Not sure yet, how reliable permitted types are. For now, we just log an error
	# instead of raising an exception or returning.
	if intraday and "C52" not in permitted_types:
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"It seems like EBICS User {0} lacks permission 'C52' for downloading intraday transactions. "
				"The permitted types are: {1}."
			).format(user.name, ", ".join(permitted_types)),
			reference_doctype="EBICS User",
			reference_name=user.name,
		)

	if not intraday and "C53" not in permitted_types:
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"It seems like EBICS User {0} lacks permission 'C52' for downloading booked bank statements. "
				"The permitted types are: {1}."
			).format(user.name, ", ".join(permitted_types)),
			reference_doctype="EBICS User",
			reference_name=user.name,
		)

	if not intraday and user.split_batch_transactions and "C54" not in permitted_types:
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"EBICS User {0} lacks permission 'C54' for splitting batch transactions. "
				"The permitted types are: {1}."
			).format(user.name, ", ".join(permitted_types)),
			reference_doctype="EBICS User",
			reference_name=user.name,
		)


def get_bank_account(iban: str, bank: str, company: str) -> str | None:
	return frappe.db.get_value(
		"Bank Account",
		{
			"iban": iban,
			"disabled": 0,
			"bank": bank,
			"is_company_account": 1,
			"company": company,
		},
	)


def process_camt_document(
	camt_document,
	bank_account: str,
	company: "str | None" = None,
	earliest_date: "date | None" = None,
	split_batch_transactions: bool = False,
):
	if not company:
		company = frappe.db.get_value("Bank Account", bank_account, "company")

	if camt_document._type in ("camt.053.001.08", "camt.052.001.08"):
		# Recognize a batch solely by the presence of the Btch element or more than one subtransaction.
		camt_document._strict_batch_parsing = True

	for transaction in camt_document:
		if transaction.status and transaction.status != "BOOK":
			# Skip PDNG and INFO transactions
			continue

		if (
			transaction.batch
			and (split_batch_transactions or len(transaction) == 1)
			and len(transaction) >= 1
		):
			# Split batch transactions into sub-transactions, based on info
			# from camt.054 that is sometimes available.
			# If that's not possible, create a single transaction
			for sub_transaction in transaction:
				_create_bank_transaction(
					bank_account,
					company,
					sub_transaction,
					earliest_date,
				)
		else:
			_create_bank_transaction(
				bank_account,
				company,
				transaction,
				earliest_date,
			)


def _create_bank_transaction(
	bank_account: str,
	company: str,
	sepa_transaction: "SEPATransaction",
	start_date: "date | None" = None,
):
	"""Create an ERPNext Bank Transaction from a given fintech.sepa.SEPATransaction.

	https://www.joonis.de/en/fintech/doc/sepa/#fintech.sepa.SEPATransaction
	"""
	# sepa_transaction.bank_reference can be None, but we can still find an ID in the XML
	# For our test bank, the latter is a timestamp with nanosecond accuracy.
	transaction_id = sepa_transaction.bank_reference or sepa_transaction._xmlobj.Refs.TxId.text

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

	bt.description = "\n".join(sepa_transaction.purpose) or sepa_transaction.info
	bt.reference_number = sepa_transaction.eref
	bt.transaction_id = transaction_id
	bt.bank_party_iban = sepa_transaction.iban
	bt.bank_party_name = sepa_transaction.name

	with contextlib.suppress(frappe.exceptions.UniqueValidationError):
		bt.insert()
		bt.submit()


def log_request(
	ebics_user: str,
	order_type: str,
	requested_by: Literal["User", "System"],
	parameters: dict,
):
	request = frappe.new_doc("EBICS Request")
	request.ebics_user = ebics_user
	request.order_type = order_type
	request.requested_by = requested_by
	request.parameters = json.dumps(parameters, indent=2)
	return request.save(ignore_permissions=True)


def get_protocol_versions(ebics_host_id: str, ebics_url: str):
	"""Return a list of protocol versions supported by the bank."""
	register_fintech()

	from fintech.ebics import EbicsBank, EbicsKeyRing

	keyring = EbicsKeyRing({})
	bank = EbicsBank(keyring, ebics_host_id, ebics_url)

	return bank.get_protocol_versions()


@frappe.whitelist()
def upload_camt_file():
	frappe.has_permission("Bank Transaction", "create", throw=True)

	file_bytes = frappe.local.uploaded_file
	bank_account = frappe.form_dict.docname

	register_fintech()

	from fintech.sepa import CAMTDocument

	camt_document = CAMTDocument(file_bytes.decode())
	process_camt_document(camt_document, bank_account)


def register_fintech(needs_license_key: bool = False):
	banking_settings = frappe.get_single("Banking Settings")

	licensee_name = banking_settings.fintech_licensee_name or None
	license_key = None
	with contextlib.suppress(frappe.AuthenticationError, frappe.ValidationError):
		license_key = banking_settings.get_password("fintech_license_key")

	if needs_license_key and not license_key:
		frappe.throw(
			_(
				"License key not found. Please activate the checkbox 'Enable EBICS' in the {0} and "
				"ensure that your subscription is active."
			).format(get_link_to_form("Banking Settings", "Banking Settings"))
		)

	try:
		fintech.register(
			name=licensee_name,
			keycode=license_key,
		)
	except RuntimeError as e:
		if e.args[0] != "'register' can be called only once":
			raise e
