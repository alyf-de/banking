import contextlib
import hashlib
import json
from typing import TYPE_CHECKING, Literal

import fintech
import frappe
from frappe import _
from frappe.utils.data import get_link_to_form

from banking.ebics.manager import EBICSManager
from banking.ebics.types import MT940Statement, MT940Transaction

if TYPE_CHECKING:
	from datetime import date

	from fintech.sepa import SEPATransaction

	from banking.ebics.doctype.ebics_user.ebics_user import EBICSUser
	from banking.overrides.bank_transaction import CustomBankTransaction


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

	manager = EBICSManager(
		protocol_version=ebics_user.protocol_version,
		country_code=ebics_user.get_country_code(),
	)
	manager.set_keyring(
		keys=ebics_user.get_keyring(),
		save_to_db=ebics_user.store_keyring,
		passphrase=passphrase or ebics_user.get_passphrase(),
		sig_passphrase=sig_passphrase,
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

	from fintech.sepa import (
		CAMTDocument,
	)  # import possible only after manager is initialized

	permitted_types = manager.get_permitted_order_types()
	validate_permitted_types(user, permitted_types, intraday)

	with_c54 = user.download_batch_transactions and set(permitted_types).intersection({"C54", "Z54"})
	request = log_request(
		ebics_user,
		("Z52" if manager.country_code == "CH" else "C52")
		if intraday
		else ("Z53" if manager.country_code == "CH" else "C53"),
		requested_by,
		{
			"start_date": start_date,
			"end_date": end_date,
		},
	)
	main_xml, batch_xml = None, None
	try:
		# Use the manager's download methods which handle protocol version automatically
		if intraday:
			main_xml = manager.download_c52(start_date, end_date)
		else:
			main_xml = manager.download_c53(start_date, end_date)

		if with_c54:
			batch_xml = manager.download_c54(start_date, end_date)

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
		manager.confirm_download(success=False)
		return

	manager.confirm_download(success=True)


def validate_permitted_types(user, permitted_types, intraday: bool):
	# Not sure yet, how reliable permitted types are. For now, we just log an error
	# instead of raising an exception or returning.
	if intraday and not set(permitted_types).intersection({"C52", "Z52"}):
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"It seems like EBICS User {0} lacks permission 'C52' for downloading intraday transactions. The permitted types are: {1}."
			).format(user.name, ", ".join(permitted_types)),
			reference_doctype="EBICS User",
			reference_name=user.name,
		)

	if not intraday and not set(permitted_types).intersection({"C53", "Z53"}):
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"It seems like EBICS User {0} lacks permission 'C52' for downloading booked bank statements. The permitted types are: {1}."
			).format(user.name, ", ".join(permitted_types)),
			reference_doctype="EBICS User",
			reference_name=user.name,
		)

	if (
		not intraday
		and user.download_batch_transactions
		and not set(permitted_types).intersection({"C54", "Z54"})
	):
		frappe.log_error(
			title=_("Banking Error"),
			message=_(
				"EBICS User {0} lacks permission 'C54' for downloading batch transactions. The permitted types are: {1}."
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
				create_sepa_bank_transaction(
					bank_account,
					company,
					sub_transaction,
					earliest_date,
				)
		else:
			create_sepa_bank_transaction(
				bank_account,
				company,
				transaction,
				earliest_date,
			)


def create_sepa_bank_transaction(
	bank_account: str,
	company: str,
	sepa_transaction: "SEPATransaction",
	start_date: "date | None" = None,
):
	"""Create an ERPNext Bank Transaction from a given fintech.sepa.SEPATransaction.

	https://www.joonis.de/en/fintech/doc/sepa/#fintech.sepa.SEPATransaction
	"""
	if start_date and sepa_transaction.date < start_date:
		return

	values_to_hash = [
		sepa_transaction.date,
		sepa_transaction.iban,
		sepa_transaction.name,
		sepa_transaction.eref,
		sepa_transaction.amount.value,
		sepa_transaction.amount.currency,
		sepa_transaction.info,
		*sepa_transaction.purpose,
	]

	amount = float(sepa_transaction.amount.value)
	create_bank_transaction(
		bank_account=bank_account,
		transaction_id=(
			# sepa_transaction.bank_reference can be None, but we can still find an ID in the XML
			# For our test bank, the latter is a timestamp with nanosecond accuracy.
			sepa_transaction.bank_reference
			or sepa_transaction._xmlobj.Refs.TxId.text
			or get_transaction_hash(values_to_hash)
		),
		company=company,
		currency=sepa_transaction.amount.currency,
		description="\n".join(sepa_transaction.purpose) or sepa_transaction.info,
		deposit=max(amount, 0),
		withdrawal=abs(min(amount, 0)),
		date=sepa_transaction.date,
		reference_number=sepa_transaction.eref,
		bank_party_name=sepa_transaction.ultimate_name or sepa_transaction.name,
		bank_party_iban=sepa_transaction.iban,
	)


def get_transaction_hash(transaction: list):
	sha = hashlib.sha256()
	for value in transaction:
		if value:
			sha.update(frappe.safe_encode(str(value)))

	return sha.hexdigest()


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


@frappe.whitelist()
def upload_mt940_file():
	frappe.has_permission("Bank Transaction", "create", throw=True)

	file_bytes = frappe.local.uploaded_file
	bank_account = frappe.form_dict.docname

	register_fintech()

	from fintech.swift import parse_mt940

	mt940_data = file_bytes.decode()
	statements: list[MT940Statement] = parse_mt940(mt940_data)

	for statement in statements:
		process_mt940_statement(statement, bank_account)


def process_mt940_statement(statement: MT940Statement, bank_account: str):
	"""Process a single MT940 statement and create bank transactions"""

	company = frappe.db.get_value("Bank Account", bank_account, "company")
	currency = statement["balance_open"]["currency"]
	for transaction in statement["transactions"]:
		create_mt940_bank_transaction(bank_account, company, transaction, currency)


def create_mt940_bank_transaction(
	bank_account: str, company: str, transaction: MT940Transaction, currency: str
):
	"""Create a bank transaction from MT940 transaction data"""
	transaction_date = transaction.get("date") or transaction["valuta"]
	party_iban = transaction.get("iban") or transaction.get("account")
	party_name = transaction.get("sepa", {}).get("ABWA") or "".join(transaction.get("name", []))
	reference = (
		transaction.get("sepa", {}).get("EREF")
		or transaction["reference"]
		or transaction["bank_reference"]
		or ""
	)
	transaction_type = transaction.get("booking_text")
	amount = transaction["amount"]
	description = (
		transaction.get("description")
		or transaction.get("sepa", {}).get("SVWZ")
		or " ".join(transaction.get("purpose", []))
	)

	values_to_hash = [
		transaction_date,
		party_iban,
		party_name,
		reference,
		amount,
		currency,
		transaction_type,
		description,
	]

	create_bank_transaction(
		bank_account=bank_account,
		transaction_id=get_transaction_hash(values_to_hash),
		company=company,
		currency=currency,
		description=description,
		deposit=max(amount, 0),
		withdrawal=abs(min(amount, 0)),
		transaction_type=transaction_type,
		date=transaction_date,
		reference_number="" if reference == "NONREF" else reference,
		bank_party_name=party_name,
		bank_party_iban=party_iban,
	)


def create_bank_transaction(
	bank_account: str,
	transaction_id: str,
	**kwargs,
):
	"""Create a bank transaction from the given kwargs."""
	# NOTE: This does not work for old data, this ID is different from Kosma's.
	if frappe.db.exists(
		"Bank Transaction",
		{"transaction_id": transaction_id, "bank_account": bank_account},
	):
		return

	bt: CustomBankTransaction = frappe.new_doc("Bank Transaction")
	bt.bank_account = bank_account
	bt.transaction_id = transaction_id
	bt.update(kwargs)

	with contextlib.suppress(frappe.exceptions.UniqueValidationError):
		bt.insert()
		bt.submit()


def register_fintech(needs_license_key: bool = False):
	banking_settings = frappe.get_single("Banking Settings")

	licensee_name = banking_settings.fintech_licensee_name or None
	license_key = None
	with contextlib.suppress(frappe.AuthenticationError, frappe.ValidationError):
		license_key = banking_settings.get_password("fintech_license_key")

	if needs_license_key and not license_key:
		frappe.throw(
			_(
				"License key not found. Please activate the checkbox 'Enable EBICS' in the {0} and ensure that your subscription is active."
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
