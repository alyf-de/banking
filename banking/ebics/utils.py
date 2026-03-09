import contextlib
import hashlib
import json
from typing import TYPE_CHECKING, Literal

import fintech
import frappe
from frappe import _
from frappe.utils import is_valid_iban
from frappe.utils.data import get_link_to_form

from banking.ebics.manager import EBICSManager, EbicsRequest
from banking.ebics.types import MT940Statement, MT940Transaction


class UnresolvedBatchTransactionError(Exception):
	"""Raised when a batch transaction cannot be resolved due to missing camt.054 data.

	This is a transient error - the camt.054 file may become available on a later sync.
	Scheduled jobs should catch this and log a warning instead of failing the entire sync.
	"""

	pass


if TYPE_CHECKING:
	from datetime import date

	from fintech.sepa import CAMTDocument, SEPATransaction

	from banking.ebics.doctype.ebics_request.ebics_request import EBICSRequest as EBICSRequestDoc
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


def get_request_map(
	country_code: str | None = None, start_date: str | None = None, end_date: str | None = None
) -> dict[str, EbicsRequest]:
	"""Get EbicsRequest for the given country. Switzerland uses Z-types, others use C-types."""
	prefix = "Z" if country_code == "CH" else "C"
	return {
		"intraday": EbicsRequest(
			order_type=f"{prefix}52",
			camt_msg="camt.052",
			service="STM",
			start_date=start_date,
			end_date=end_date,
		),
		"statement": EbicsRequest(
			order_type=f"{prefix}53",
			camt_msg="camt.053",
			service="EOP",
			start_date=start_date,
			end_date=end_date,
		),
		"batch": EbicsRequest(
			order_type=f"{prefix}54",
			camt_msg="camt.054",
			service="STM",
			start_date=start_date,
			end_date=end_date,
		),
	}


def execute_ebics_download(
	manager: EBICSManager,
	ebics_user: str,
	ebics_request: EbicsRequest,
	requested_by: Literal["User", "System"],
	permitted_types: list[str],
) -> tuple[dict | None, "EBICSRequestDoc"]:
	"""Execute a single EBICS download request with logging and error handling.

	Args:
		manager: The EBICS manager instance
		ebics_user: The EBICS User name
		ebics_request: The request to execute
		requested_by: Who initiated the request
		permitted_types: List of permitted order types for validation

	Returns:
		tuple: (downloaded XML files or None, request log document)
	"""
	if manager.protocol_version == "H004":
		validated_perms(ebics_user, permitted_types, ebics_request.order_type)
	elif manager.protocol_version == "H005":
		validated_perms(
			ebics_user,
			permitted_types,
			("BTD", ebics_request.service, ebics_request.camt_msg),
		)

	request_log = log_request(
		ebics_user,
		ebics_request.order_type,
		requested_by,
		{
			"start_date": ebics_request.start_date,
			"end_date": ebics_request.end_date,
		},
	)

	try:
		xml_files = manager.download(ebics_request)

		request_log.db_set(
			{
				"status": "Successful",
				"response": json.dumps(
					{file_name: file.decode() for file_name, file in xml_files.items()},
					indent=2,
				),
			}
		)
		return xml_files, request_log
	except fintech.ebics.EbicsNoDataAvailable:
		request_log.db_set({"status": "Successful", "response": "No Data Available"})
	except Exception as e:
		request_log.db_set({"status": "Failed", "response": str(e)})
		frappe.log_error(
			title=_("Banking Error"),
			reference_doctype="EBICS User",
			reference_name=ebics_user,
		)

	return None, request_log


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

	request_map = get_request_map(manager.country_code, start_date, end_date)
	main_request = request_map["intraday"] if intraday else request_map["statement"]

	# Get permitted types once - they don't change across downloads
	permitted_types = manager.get_permitted_order_types()

	# Download main statements
	main_xml, main_request_log = execute_ebics_download(
		manager, user.name, main_request, requested_by, permitted_types
	)
	if not main_xml:
		return

	# Download batch transactions if enabled
	batch_xml = None
	if user.download_batch_transactions:
		batch_request = request_map["batch"]
		batch_xml, _batch_request_log = execute_ebics_download(
			manager, user.name, batch_request, requested_by, permitted_types
		)
		# Continue even if batch download fails - main_xml is what matters

	# Keep the request logs, no matter what happens next.
	frappe.db.commit()

	# We want to process either all documents or none. If we fail to process one, we
	# want to rollback the entire transaction and report an error.
	try:
		import_ebics_json(user, main_xml, batch_xml)
	except UnresolvedBatchTransactionError:
		# This is a transient error - camt.054 may become available on the next sync.
		# Log a warning instead of an error and tell the bank to resend the data.
		frappe.db.rollback()
		main_request_log.db_set("status", "Skipped")
		frappe.log_error(
			title=_("Banking Warning"),
			message=_("Unable to resolve batch transaction: camt.054 not available. Please try again later."),
			reference_doctype="EBICS User",
			reference_name=user.name,
		)
		manager.confirm_download(success=False)
		return
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title=_("Banking Error"),
			reference_doctype="EBICS User",
			reference_name=user.name,
		)
		manager.confirm_download(success=False)
		return

	manager.confirm_download(success=True)


def import_ebics_json(user: "EBICSUser", main_data: dict, batch_data: dict | None = None):
	"""Import EBICS transactions from the given JSON data, considering user settings.

	NOTE: fintech needs to be registered before calling this function.

	Args:
		user: An EBICS User record
		main_data: Dictionary of XML files by name, e.g. {"camt053.xml": "<xml>...</xml>"}
		batch_data: Dictionary of XML files by name, or None if batch transactions are not enabled
	"""
	from fintech.sepa import CAMTDocument

	for name in sorted(main_data):
		camt_document = CAMTDocument(xml=main_data[name], camt54=batch_data)
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


def validated_perms(ebics_user, permitted_types, required_type):
	# Not sure yet, how reliable permitted types are. For now, we just log an error
	# instead of raising an exception or returning.
	if required_type not in permitted_types:
		frappe.log_error(
			title=_("Banking Warning"),
			message=_(
				"It seems like the EBICS User lacks permissions for order type '{0}'. The permitted types are: {1}."
			).format(required_type, ", ".join(str(t) for t in permitted_types)),
			reference_doctype="EBICS User",
			reference_name=ebics_user,
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
	camt_document: "CAMTDocument",
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

		transaction_id = get_transaction_id(transaction)

		if transaction.batch and split_batch_transactions:
			# Split batch transactions into sub-transactions, based on info from camt.054.

			if len(transaction) == 0:
				# camt.054 might become available at a later time than camt.053.
				# In this case, we want to block the processing of camt.053 until camt.054 is available.
				raise UnresolvedBatchTransactionError()

			for sub_transaction_index, sub_transaction in enumerate(transaction):
				sub_transaction_id = get_transaction_id(sub_transaction, sub_transaction_index)
				create_sepa_bank_transaction(
					bank_account,
					company,
					sub_transaction,
					transaction_id=transaction_id,
					subtransaction_id=sub_transaction_id,
					start_date=earliest_date,
				)
		else:
			create_sepa_bank_transaction(
				bank_account,
				company,
				transaction,
				transaction_id=transaction_id,
				start_date=earliest_date,
			)


def create_sepa_bank_transaction(
	bank_account: str,
	company: str,
	sepa_transaction: "SEPATransaction",
	transaction_id: str,
	subtransaction_id: str | None = None,
	start_date: "date | None" = None,
):
	"""Create an ERPNext Bank Transaction from a given fintech.sepa.SEPATransaction.

	https://www.joonis.de/en/fintech/doc/sepa/#fintech.sepa.SEPATransaction
	"""
	if start_date and sepa_transaction.date < start_date:
		return

	amount = float(sepa_transaction.amount.value)
	currency = sepa_transaction.amount.currency
	party_iban, party_account_number = get_iban_or_account_number(sepa_transaction.iban)

	create_bank_transaction(
		bank_account=bank_account,
		transaction_id=transaction_id,
		subtransaction_id=subtransaction_id,
		company=company,
		currency=currency,
		description="\n".join(sepa_transaction.purpose) or sepa_transaction.info,
		deposit=max(amount, 0),
		withdrawal=abs(min(amount, 0)),
		date=sepa_transaction.date,
		reference_number=sepa_transaction.eref,
		bank_party_name=sepa_transaction.ultimate_name
		or sepa_transaction.name
		or (
			# some swiss banks specify the address only
			", ".join(sepa_transaction.address) if sepa_transaction.address else None
		),
		bank_party_iban=party_iban,
		bank_party_account_number=party_account_number,
		included_fee=parse_included_fees(sepa_transaction, currency),
	)


def parse_included_fees(
	sepa_transaction: "SEPATransaction", transaction_currency: str | None = None
) -> float:
	def _parse_amount(value) -> float:
		if isinstance(value, str):
			normalized_value = value.strip().replace(",", ".")
			if not normalized_value:
				return 0.0
			with contextlib.suppress(ValueError):
				return float(normalized_value)
			return 0.0

		with contextlib.suppress(TypeError, ValueError):
			return float(value)
		return 0.0

	def _normalize_currency(value) -> str | None:
		if not isinstance(value, str):
			return None
		normalized = value.strip().upper()
		return normalized or None

	charges = sepa_transaction._xmlobj.Chrgs.TtlChrgsAndTaxAmt
	charges_currency = _normalize_currency(
		charges.attrib.get("Ccy") if isinstance(charges.attrib, dict) else None
	)
	expected_currency = _normalize_currency(transaction_currency)
	if expected_currency and charges_currency and expected_currency != charges_currency:
		return 0.0

	# This is the gross amount including taxes.
	# The tax amount can be found in sepa_transaction._xmlobj.Tax.TtlTaxAmt._text
	taxes_and_charges = _parse_amount(charges._text)
	return taxes_and_charges


def get_transaction_hash(transaction: list):
	sha = hashlib.sha256()
	for value in transaction:
		if value:
			sha.update(frappe.safe_encode(str(value)))

	return sha.hexdigest()


def get_transaction_id(sepa_transaction: "SEPATransaction", subtransaction_index: int | None = None):
	"""Return a transaction ID for the given SEPA transaction.

	If a subtransaction index is provided, the transaction is treated as a sub-transaction.
	"""
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

	if subtransaction_index is not None:
		if sepa_transaction._xmlobj.Refs.TxId.text:
			return sepa_transaction._xmlobj.Refs.TxId.text
		elif sepa_transaction.bank_reference:
			return f"{sepa_transaction.bank_reference}-{subtransaction_index}"
		else:
			return get_transaction_hash(values_to_hash)
	else:
		return (
			# sepa_transaction.bank_reference can be None, but we can still find an ID in the XML
			# For our test bank, the latter is a timestamp with nanosecond accuracy.
			sepa_transaction.bank_reference
			or sepa_transaction._xmlobj.Refs.TxId.text
			or get_transaction_hash(values_to_hash)
		)


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
	process_camt_document(camt_document, bank_account, split_batch_transactions=False)


def decode_mt940_bytes(file_bytes: bytes) -> str:
	"""Decode MT940 file bytes by trying common encodings (UTF-8, CP1252, Latin-1)."""
	for encoding in ("utf-8", "cp1252"):
		try:
			return file_bytes.decode(encoding)
		except UnicodeDecodeError:
			continue

	return file_bytes.decode("latin-1")


@frappe.whitelist()
def upload_mt940_file():
	frappe.has_permission("Bank Transaction", "create", throw=True)

	file_bytes = frappe.local.uploaded_file
	bank_account = frappe.form_dict.docname

	register_fintech()

	from fintech.swift import parse_mt940

	mt940_data = decode_mt940_bytes(file_bytes)
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

	party_iban, party_account_number = get_iban_or_account_number(party_iban)

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
		bank_party_account_number=party_account_number,
	)


def get_iban_or_account_number(number: str) -> tuple[str | None, str | None]:
	"""Return a tuple of (iban, account_number) for the given number.

	If the number is a valid IBAN, account_number is None.
	Otherwise, iban is None and account_number is the given number.
	"""
	if is_valid_iban(number):
		return number, None

	return None, number


def create_bank_transaction(
	bank_account: str,
	transaction_id: str,
	subtransaction_id: str | None = None,
	**kwargs,
):
	"""Create a bank transaction from the given kwargs.

	NOTE: This does not prevent duplicate transactions for old data, this ID is
	different from Kosma's.
	"""
	if subtransaction_id:
		# Check if we have already created a single batch transaction.
		# Then this subtransaction would be a duplicate resulting from changed batch-splitting settings.
		if frappe.db.exists(
			"Bank Transaction",
			{
				"transaction_id": transaction_id,
				"bank_account": bank_account,
				"subtransaction_id": ("is", "not set"),
			},
		):
			return

		# Check if this subtransaction has already been created.
		if frappe.db.exists(
			"Bank Transaction",
			{
				"transaction_id": transaction_id,
				"bank_account": bank_account,
				"subtransaction_id": subtransaction_id,
			},
		):
			return
	elif frappe.db.exists(
		"Bank Transaction",
		{"transaction_id": transaction_id, "bank_account": bank_account},
	):
		# This is not a subtransaction and we have already created a transaction with this ID.
		# We should only allow additional subtransactions.
		return

	bt: CustomBankTransaction = frappe.new_doc("Bank Transaction")
	bt.bank_account = bank_account
	bt.transaction_id = transaction_id
	bt.subtransaction_id = subtransaction_id
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
