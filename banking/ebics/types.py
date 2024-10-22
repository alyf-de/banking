"""With friendly permission of joonis new media, the official documentation at
https://www.joonis.de/en/fintech/doc/ was used to create the docstrings for this file.

Copyright © 2024 by joonis new media - All rights reserved.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Iterator


class Amount:
	"""The Amount class with an integrated currency converter.

	Arithmetic operations can be performed directly on this object.
	"""

	default_currency: str = "EUR"
	exchange_rates: dict[str, Decimal] = {}

	def __init__(self, value: Decimal, currency: str | None = None):
		"""Initializes the Amount instance.

		Parameters:
		* value - The amount value.
		* currency - An ISO-4217 currency code. If not specified, it is set to the value of the class attribute default_currency which is initially set to EUR.
		"""
		...

	def convert(self, currency: str) -> "Amount":
		"""Converts the amount to another currency on the basis of the current exchange rates provided by the European Central Bank. The exchange rates are automatically updated once a day and cached in memory for further usage.

		Parameters:
		* currency - The ISO-4217 code of the target currency.

		Returns: An Amount object in the requested currency.
		"""
		...

	@property
	def currency(self) -> str:
		"""The ISO-4217 currency code."""
		...

	@property
	def decimals(self) -> int:
		"""The number of decimal places (at least 2). Use the built-in round to adjust the decimal places."""
		...

	@classmethod
	def update_exchange_rates(cls) -> bool:
		"""Updates the exchange rates based on the data provided by the European Central Bank and stores it in the class attribute exchange_rates. Usually it is not required to call this method directly, since it is called automatically by the method convert().

		Returns: A boolean flag whether updated exchange rates were available or not.
		"""
		...

	@property
	def value(self) -> Decimal:
		"""The amount value of type decimal.Decimal."""
		...


class Mandate:
	"""SEPA mandate class."""

	def __init__(self, path: str):
		"""Initializes the SEPA mandate instance.

		Parameters:
		* path - The path to a SEPA PDF file.
		"""
		...

	@property
	def b2b(self) -> bool:
		"""Flag if it is a B2B mandate (read-only)."""
		...

	@property
	def cid(self) -> str:
		"""The creditor id (read-only)."""
		...

	@property
	def closed(self) -> bool:
		"""Flag if the mandate is closed (read-only)."""
		...

	@property
	def created(self) -> str:
		"""The creation date (read-only)."""
		...

	@property
	def creditor(self) -> str | dict:
		"""The creditor account (read-only)."""
		...

	@property
	def debtor(self) -> str | dict:
		"""The debtor account (read-only)."""
		...

	@property
	def executed(self) -> str | None:
		"""The last execution date (read-only)."""
		...

	def is_valid(self) -> bool:
		"""Checks if this SEPA mandate is still valid."""
		...

	@property
	def modified(self) -> str:
		"""The last modification date (read-only)."""
		...

	@property
	def mref(self) -> str:
		"""The mandate reference (read-only)."""
		...

	@property
	def pdf_path(self) -> str:
		"""The path to the PDF file (read-only)."""
		...

	@property
	def recurrent(self) -> bool:
		"""Flag whether this mandate is recurrent or not."""
		...

	@property
	def signed(self) -> str:
		"""The date of signature (read-only)."""
		...


class Account:
	"""Account class for managing SEPA-related account information."""

	def __init__(
		self,
		iban: str | tuple[str, str],
		name: str,
		country: str | None = None,
		city: str | None = None,
		postcode: str | None = None,
		street: str | None = None,
	):
		"""Initializes the account instance.

		Parameters:
		* iban - Either the IBAN or a 2-tuple in the form of either (IBAN, BIC) or (ACCOUNT_NUMBER, BANK_CODE). The latter will be converted to the corresponding IBAN automatically. An IBAN is checked for validity.
		* name - The name of the account holder.
		* country - The country (ISO-3166 ALPHA 2) of the account holder (optional).
		* city - The city of the account holder (optional).
		* postcode - The postcode of the account holder (optional).
		* street - The street of the account holder (optional).
		"""
		...

	@property
	def address(self) -> tuple[str, ...]:
		"""Tuple of unstructured address lines (read-only)."""
		...

	@property
	def bic(self) -> str:
		"""The BIC of this account (read-only)."""
		...

	@property
	def cid(self) -> str:
		"""The creditor id of the account holder (readonly)."""
		...

	@property
	def city(self) -> str:
		"""The city of the account holder (read-only)."""
		...

	@property
	def country(self) -> str:
		"""The country of the account holder (read-only)."""
		...

	@property
	def cuc(self) -> str:
		"""The CBI unique code (CUC) of the account holder (readonly)."""
		...

	@property
	def iban(self) -> str:
		"""The IBAN of this account (read-only)."""
		...

	def is_sepa(self) -> bool:
		"""Checks if this account seems to be valid within the Single Euro Payments Area."""
		...

	@property
	def mandate(self) -> Mandate:
		"""The assigned mandate (read-only)."""
		...

	@property
	def name(self) -> str:
		"""The name of the account holder (read-only)."""
		...

	@property
	def postcode(self) -> str:
		"""The postcode of the account holder (read-only)."""
		...

	def set_mandate(
		self, mref: str, signed: str | date, recurrent: bool = False
	) -> Mandate:
		"""Sets the SEPA mandate for this account.

		Parameters:
		* mref - The mandate reference.
		* signed - The date of signature. Can be a date object or an ISO8601 formatted string.
		* recurrent - Flag whether this is a recurrent mandate or not.

		Returns: A Mandate object.
		"""
		...

	def set_originator_id(self, cid: str | None = None, cuc: str | None = None) -> None:
		"""Sets the originator id of the account holder.

		Parameters:
		* cid - The SEPA creditor id. Required for direct debits and in some countries also for credit transfers.
		* cuc - The CBI unique code (only required in Italy).
		"""
		...

	def set_ultimate_name(self, name: str) -> None:
		"""Sets the ultimate name used for SEPA transactions and by the MandateManager.

		Parameters:
		* name - The ultimate name for SEPA transactions.
		"""
		...

	@property
	def street(self) -> str:
		"""The street of the account holder (read-only)."""
		...

	@property
	def ultimate_name(self) -> str:
		"""The ultimate name used for SEPA transactions."""
		...


class SEPATransaction:
	"""The SEPATransaction class.

	This class cannot be instantiated directly. An instance is returned by the method
	add_transaction() of a SEPA document instance or by the iterator of a CAMTDocument instance.

	If it is a batch of other transactions, the instance can be treated as an iterable
	over all underlying transactions.
	"""

	@property
	def address(self) -> tuple[str, str]:
		"""A tuple which holds the address of the remote account holder."""
		...

	@property
	def amount(self) -> "Amount":
		"""The transaction amount of type Amount. Debits are always signed negative."""
		...

	@property
	def bank_reference(self) -> str:
		"""The bank reference, used to uniquely identify a transaction."""
		...

	@property
	def batch(self) -> bool:
		"""Flag which indicates a batch transaction."""
		...

	@property
	def bic(self) -> str:
		"""The BIC of the remote account (BIC)."""
		...

	@property
	def camt_reference(self) -> str:
		"""The reference to a CAMT file."""
		...

	@property
	def cheque(self) -> str:
		"""The cheque number."""
		...

	@property
	def classification(self) -> str | tuple[str, str, str, str]:
		"""The transaction classification.

		For German banks it is a tuple in the form of (SWIFTCODE, GVC, PRIMANOTA, TEXTKEY),
		for French banks a tuple in the form of (DOMAINCODE, FAMILYCODE, SUBFAMILYCODE, TRANSACTIONCODE),
		otherwise a plain string.
		"""
		...

	@property
	def country(self) -> str:
		"""The country of the remote account holder."""
		...

	@property
	def date(self) -> str | date:
		"""The booking date or appointed due date."""
		...

	@property
	def eref(self) -> str:
		"""The end-to-end reference (EREF)."""
		...

	def get_account(self) -> Account:
		"""Returns an Account instance of the remote account."""
		...

	@property
	def iban(self) -> str:
		"""The IBAN of the remote account (IBAN)."""
		...

	@property
	def info(self) -> str:
		"""The transaction information (BOOKINGTEXT)."""
		...

	@property
	def kref(self) -> str:
		"""The id of the logical PAIN file (KREF)."""
		...

	@property
	def mref(self) -> str:
		"""The mandate reference (MREF)."""
		...

	@property
	def msgid(self) -> str:
		"""The message id of the physical PAIN file."""
		...

	@property
	def name(self) -> str:
		"""The name of the remote account holder."""
		...

	@property
	def originator_id(self) -> str:
		"""The creditor or debtor id of the remote account (CRED/DEBT)."""
		...

	@property
	def purpose(self) -> tuple[str, ...]:
		"""A tuple of the transaction purpose (SVWZ)."""
		...

	@property
	def purpose_code(self) -> str:
		"""The external purpose code (PURP)."""
		...

	@property
	def return_info(self) -> tuple[str, str]:
		"""A tuple of return code and reason."""
		...

	@property
	def reversal(self) -> bool:
		"""The reversal indicator."""
		...

	@property
	def status(self) -> str:
		"""The transaction status. A value of INFO, PDNG or BOOK."""
		...

	@property
	def ultimate_name(self) -> str:
		"""The ultimate name of the remote account (ABWA/ABWE)."""
		...

	@property
	def valuta(self) -> str | date:
		"""The value date."""
		...


class SEPACreditTransfer:
	"""
	SEPACreditTransfer class for creating SEPA credit transfer documents.
	"""

	def __init__(
		self,
		account: Account,
		type: str = "NORM",
		cutoff: int = 14,
		batch: bool = True,
		cat_purpose: str | None = None,
		scheme: str | None = None,
		currency: str | None = None,
	):
		"""Initializes the SEPA credit transfer instance.

		Parameters:
		* account – The local debtor account.
		* type – The credit transfer priority ('NORM', 'HIGH', 'URGP', or 'INST').
		* cutoff – The cut-off time of the debtor’s bank.
		* batch – Flag whether SEPA batch mode is enabled.
		* cat_purpose – The SEPA category purpose code (optional).
		* scheme – The PAIN scheme of the document (optional).
		* currency – The ISO-4217 code of the currency to use (optional).
		"""
		...

	@property
	def account(self) -> Account:
		"""The local account (read-only)."""
		...

	def add_transaction(
		self,
		account: Account,
		amount: float | "Amount",
		purpose: str | tuple[str, str],
		eref: str | None = None,
		ext_purpose: str | None = None,
		due_date: str | int | "date" | None = None,
	) -> SEPATransaction:
		"""Adds a transaction to the SEPACreditTransfer document.

		Parameters:
		* account – The remote creditor account.
		* amount – The transaction amount as a floating point number or an instance of Amount.
		* purpose – The transaction purpose text or structured reference.
		* eref – The end-to-end reference (optional).
		* ext_purpose – The SEPA external purpose code (optional).
		* due_date – The due date for the transaction (optional).

		Returns: A SEPATransaction instance.
		"""
		...

	@property
	def batch(self) -> bool:
		"""Flag if batch mode is enabled (read-only)."""
		...

	@property
	def cat_purpose(self) -> str | None:
		"""The category purpose (read-only)."""
		...

	@property
	def currency(self) -> str:
		"""The ISO-4217 currency code (read-only)."""
		...

	@property
	def cutoff(self) -> int:
		"""The cut-off time of the local bank (read-only)."""
		...

	@property
	def message_id(self) -> str:
		"""The message id of this document (read-only)."""
		...

	def new_batch(self, kref: str | None = None) -> None:
		"""Adds additional transactions to a new batch (PmtInf block).

		Parameters:
		* kref – Custom KREF (PmtInfId) for the new batch (optional).
		"""
		...

	def render(self) -> str:
		"""Renders the SEPACreditTransfer document and returns it as XML.

		Returns: The SEPACreditTransfer document in XML format.
		"""
		...

	@property
	def scheme(self) -> str:
		"""The document scheme version (read-only)."""
		...

	@property
	def scl_check(self) -> bool:
		"""Flag whether remote accounts should be verified against the SEPA Clearing Directory (read-only)."""
		...

	def send(self, ebics_client: "EbicsClient", use_ful: bool | None = None) -> str:
		"""Sends the SEPA document using the passed EBICS instance.

		Parameters:
		* ebics_client – The fintech.ebics.EbicsClient instance.
		* use_ful – Flag for using the fintech.ebics.EbicsClient.FUL() order type for uploading (optional).

		Returns: The EBICS order id.
		"""
		...

	@property
	def type(self) -> str:
		"""The credit transfer priority type (read-only)."""
		...


class SEPADirectDebit:
	"""SEPADirectDebit class"""

	def __init__(
		self,
		account: str,
		type: str = "CORE",
		cutoff: int = 36,
		batch: bool = True,
		cat_purpose: str | None = None,
		scheme: str | None = None,
		currency: str | None = None,
	):
		"""
		Initializes the SEPA direct debit instance.

		Parameters:
		* account – The local creditor account with an appointed creditor id.
		* type – The direct debit type (CORE or B2B).
		* cutoff – The cut-off time of the creditor’s bank.
		* batch – Flag if SEPA batch mode is enabled or not.
		* cat_purpose – The SEPA category purpose code. This code is used for special treatments by the local bank and is not forwarded to the remote bank. See module attribute CATEGORY_PURPOSE_CODES for possible values.
		* scheme – The PAIN scheme of the document. If not specified, the scheme is set to pain.008.001.02. In Switzerland it is set to pain.008.001.02.ch.01, in Italy to CBISDDReqLogMsg.00.01.00.
		* currency – The ISO-4217 code of the currency to use. It must match with the currency of the local account. If not specified, it defaults to the currency of the country the local IBAN belongs to.
		"""
		...

	@property
	def account(self) -> str:
		"""The local account (read-only)."""
		...

	def add_transaction(
		self,
		account: str,
		amount: float,
		purpose: str | tuple[str, str],
		eref: str | None = None,
		ext_purpose: str | None = None,
		due_date: int | str | None = None,
	) -> "SEPATransaction":
		"""
		Adds a transaction to the SEPADirectDebit document. If scl_check is set to True, it is verified that the transaction can be routed to the target bank.

		Parameters:
		* account – The remote debtor account with a valid mandate.
		* amount – The transaction amount as floating point number or an instance of Amount. In the latter case the currency must match the currency of the document.
		* purpose – The transaction purpose text. If the value matches a valid ISO creditor reference number (starting with “RF…”), it is added as a structured reference. For other structured references a tuple can be passed in the form of (REFERENCE_NUMBER, PURPOSE_TEXT).
		* eref – The end-to-end reference (optional).
		* ext_purpose – The SEPA external purpose code (optional). This code is forwarded to the remote bank and the account holder. See module attribute EXTERNAL_PURPOSE_CODES for possible values.
		* due_date – The due date. If it is an integer or None, the next possible date is calculated starting from today plus the given number of days (considering holidays, the lead time and the given cut-off time). If it is a date object or an ISO8601 formatted string, this date is used without further validation.

		Returns: A SEPATransaction instance.
		"""
		...

	@property
	def batch(self) -> bool:
		"""Flag if batch mode is enabled (read-only)."""
		...

	@property
	def cat_purpose(self) -> str | None:
		"""The category purpose (read-only)."""
		...

	@property
	def currency(self) -> str:
		"""The ISO-4217 currency code (read-only)."""
		...

	@property
	def cutoff(self) -> int:
		"""The cut-off time of the local bank (read-only)."""
		...

	@property
	def message_id(self) -> str:
		"""The message id of this document (read-only)."""
		...

	def new_batch(self, kref: str | None = None):
		"""
		After calling this method additional transactions are added to a new batch (PmtInf block). This could be useful if you want to divide transactions into different batches with unique KREF ids.

		Parameters:
		* kref – It is possible to set a custom KREF (PmtInfId) for the new batch (new in v7.2). Be aware that KREF ids should be unique over time and that all transactions must be grouped by particular SEPA specifications (date, sequence type, etc.) into separate batches. This is done automatically if you do not pass a custom KREF.
		"""
		...

	def render(self) -> str:
		"""Renders the SEPADirectDebit document and returns it as XML."""
		...

	@property
	def scheme(self) -> str:
		"""The document scheme version (read-only)."""
		...

	@property
	def scl_check(self) -> bool:
		"""
		Flag whether remote accounts should be verified against the SEPA Clearing Directory or not. The initial value is set to True if the kontocheck library is available and the local account is originated in Germany, otherwise it is set to False.
		"""
		...

	def send(self, ebics_client: "EbicsClient", use_ful: bool | None = None) -> str:
		"""
		Sends the SEPA document using the passed EBICS instance.

		Parameters:
		* ebics_client – The fintech.ebics.EbicsClient instance.
		* use_ful – Flag, whether to use the order type fintech.ebics.EbicsClient.FUL() for uploading the document or one of the suitable order types fintech.ebics.EbicsClient.CCT(), fintech.ebics.EbicsClient.CDD() or fintech.ebics.EbicsClient.CDB(). If not specified, use_ful is set to False if the local account is originated in Germany, otherwise it is set to True. With EBICS v3.0 the document is always uploaded via fintech.ebics.EbicsClient.BTU().

		Returns: The EBICS order id.
		"""
		...

	@property
	def type(self) -> str:
		"""The direct debit type (read-only)."""
		...


class EbicsKeyRing:
	"""EBICS key ring representation.

	An EbicsKeyRing instance can hold sets of private user keys and/or public bank keys.
	Private user keys are always stored AES encrypted by the specified passphrase (derivated by PBKDF2).
	For each key file on disk or same key dictionary, a singleton instance is created.
	"""

	def __init__(
		self,
		keys: str | dict,
		passphrase: str | None = None,
		sig_passphrase: str | None = None,
	):
		"""Initializes the EBICS key ring instance.

		Parameters:
		* keys - The path to a key file or a dictionary of keys. If keys is a path and the key file does not exist, it will be created as soon as keys are added. If keys is a dictionary, all changes are applied to this dictionary and the caller is responsible to store the modifications. Key files from previous PyEBICS versions are automatically converted to a new format.
		* passphrase - The passphrase by which all private keys are encrypted/decrypted.
		* sig_passphrase - A different passphrase for the signature key (optional). Useful if you want to store the passphrase to automate downloads while preventing uploads without user interaction. (New since v7.3)
		"""
		...

	def change_passphrase(
		self, passphrase: str | None = None, sig_passphrase: str | None = None
	) -> None:
		"""Changes the passphrase by which all private keys are encrypted.

		If a passphrase is omitted, it is left unchanged. The key ring is automatically updated and saved.

		Parameters:
		* passphrase - The new passphrase.
		* sig_passphrase - The new signature passphrase. (New since v7.3)
		"""
		...

	@property
	def keyfile(self) -> str:
		"""The path to the key file (read-only)."""
		...

	@property
	def pbkdf_iterations(self) -> int:
		"""The number of iterations to derivate the passphrase by the PBKDF2 algorithm.

		Initially it is set to a number that requires an approximate run time of 50 ms to perform the derivation function.
		"""
		...

	def save(self, path: str | None = None) -> None:
		"""Saves all keys to the file specified by path.

		Usually, it is not necessary to call this method, since most modifications are stored automatically.

		Parameters:
		* path - The path of the key file. If path is not specified, the path of the current key file is used.
		"""
		...

	def set_pbkdf_iterations(
		self, iterations: int = 10000, duration: float | None = None
	) -> int:
		"""Sets the number of iterations which is used to derivate the passphrase by the PBKDF2 algorithm.

		The optimal number depends on the performance of the underlying system and the use case.

		Parameters:
		* iterations - The minimum number of iterations to set.
		* duration - The target run time in seconds to perform the derivation function. A higher value results in a higher number of iterations.

		Returns: The specified or calculated number of iterations, whatever is higher.
		"""
		...


class EbicsBank:
	"""EBICS bank representation."""

	def __init__(self, keyring: "EbicsKeyRing", hostid: str, url: str):
		"""Initializes the EBICS bank instance.

		Parameters:
		* keyring - An EbicsKeyRing instance.
		* hostid - The HostID of the bank.
		* url - The URL of the EBICS server.
		"""
		...

	def activate_keys(self, fail_silently: bool = False) -> None:
		"""Activates the bank keys downloaded via EbicsClient.HPB().

		Parameters:
		* fail_silently - Flag whether to throw a RuntimeError if there exists no key to activate.
		"""
		...

	def export_keys(self) -> dict[str, str]:
		"""Exports the bank keys in PEM format.

		Returns: A dictionary with pairs of key version and PEM encoded public key.
		"""
		...

	def get_protocol_versions(self) -> dict[str, str]:
		"""Returns a dictionary of supported EBICS protocol versions. Same as calling EbicsClient.HEV()."""
		...

	@property
	def hostid(self) -> str:
		"""The HostID of the bank (read-only)."""
		...

	@property
	def keyring(self) -> "EbicsKeyRing":
		"""The EbicsKeyRing instance (read-only)."""
		...

	@property
	def url(self) -> str:
		"""The URL of the EBICS server (read-only)."""
		...


class EbicsUser:
	"""EBICS user representation."""

	def __init__(
		self,
		keyring: EbicsKeyRing,
		partnerid: str,
		userid: str,
		systemid: str | None = None,
		transport_only: bool = False,
	):
		"""Initializes the EBICS user instance.

		Parameters:
		* keyring - An EbicsKeyRing instance.
		* partnerid - The assigned PartnerID (Kunden-ID).
		* userid - The assigned UserID (Teilnehmer-ID).
		* systemid - The assigned SystemID (usually unused).
		* transport_only - Flag if the user has permission T (EBICS T). New since v7.4.
		"""
		...

	def create_certificates(
		self, validity_period: int = 5, **x509_dn: dict[str, str]
	) -> list[str]:
		"""Generates self-signed certificates for all keys that still lack a certificate and adds them to the key ring.
		May only be used for EBICS accounts whose key management is based on certificates (eg. French banks).

		Parameters:
		* validity_period - The validity period in years.
		* x509_dn - Keyword arguments representing Distinguished Names for creating self-signed certificates. Possible arguments include:
				- commonName [CN]
				- organizationName [O]
				- organizationalUnitName [OU]
				- countryName [C]
				- stateOrProvinceName [ST]
				- localityName [L]
				- emailAddress

		Returns: A list of key versions for which a new certificate was created (new since v6.4).
		"""
		...

	def create_ini_letter(
		self, bankname: str, path: str | None = None, lang: str | None = None
	) -> bytes:
		"""Creates the INI-letter as PDF document.

		Parameters:
		* bankname - The name of the bank printed on the INI-letter as the recipient. New in v7.5.1: If bankname matches a BIC and the kontockeck package is installed,
		  the SCL directory is queried for the bank name.
		* path - The destination path of the created PDF file. If not specified, the PDF will not be saved.
		* lang - ISO 639-1 language code of the INI-letter to create. Defaults to the system locale language. (New in v7.5.1: If bankname matches a BIC,
		  it first tries to get the language from the country code of the BIC).

		Returns: The PDF data as byte string if path is None.
		"""
		...

	def create_keys(self, keyversion: str = "A006", bitlength: int = 2048) -> list[str]:
		"""Generates all missing keys required for a new EBICS user. The key ring is automatically updated and saved.

		Parameters:
		* keyversion - The key version of the electronic signature. Supported versions are A005 (based on RSASSA-PKCS1-v1_5) and A006 (based on RSASSA-PSS).
		* bitlength - The bit length of the generated keys, must be between 2048 and 4096 (default is 2048).

		Returns: A list of created key versions (new since v6.4).
		"""
		...

	def export_certificates(self) -> dict[str, list[str]]:
		"""Exports the user certificates in PEM format.

		Returns: A dictionary with pairs of key version and a list of PEM-encoded certificates (the certificate chain).
		"""
		...

	def export_keys(self, passphrase: str, pkcs: int = 8) -> dict[str, str]:
		"""Exports the user keys in encrypted PEM format.

		Parameters:
		* passphrase - The passphrase by which all keys are encrypted. The encryption algorithm depends on the used cryptography library.
		* pkcs - The PKCS version. An integer of either 1 or 8.

		Returns: A dictionary with pairs of key version and PEM-encoded private key.
		"""
		...

	def import_certificates(self, **certs: dict[str, bytes | list[bytes]]) -> None:
		"""Imports certificates from a set of keyword arguments. It verifies that the certificates match the existing keys.
		If a signature key is missing, the public key is added from the certificate. The key ring is automatically updated and saved.
		May only be used for EBICS accounts whose key management is based on certificates (eg. French banks).

		Parameters:
		* certs - Keyword arguments represent the different certificates to import. The keyword name represents the key version assigned to it.
		  The value can be a byte string of the certificate or a list of byte strings (certificate chain), either in DER or PEM format.
		  Supported keywords are: A006, A005, X002, E002.
		"""
		...

	def import_keys(
		self, passphrase: str | None = None, **keys: dict[str, bytes]
	) -> None:
		"""Imports private user keys from a set of keyword arguments. The key ring is automatically updated and saved.

		Parameters:
		* passphrase - The passphrase if the keys are encrypted. Only DES or 3TDES encrypted keys are supported.
		* keys - Keyword arguments representing the private keys to import. The keyword name represents the key version, and the value is the byte string
		  of the corresponding key, either in DER or PEM format (PKCS#1 or PKCS#8). Supported keys include:
				- A006: The signature key (RSASSA-PSS)
				- A005: The signature key (RSASSA-PKCS1-v1_5)
				- X002: The authentication key
				- E002: The encryption key
		"""
		...

	@property
	def keyring(self) -> "EbicsKeyRing":
		"""The EbicsKeyRing instance (read-only)."""
		...

	@property
	def manual_approval(self) -> bool:
		"""If uploaded orders are approved manually via accompanying document, this property must be set to True. Deprecated, use class parameter transport_only instead."""
		...

	@property
	def partnerid(self) -> str:
		"""The PartnerID of the EBICS account (read-only)."""
		...

	@property
	def systemid(self) -> str:
		"""The SystemID of the EBICS account (read-only)."""
		...

	@property
	def transport_only(self) -> bool:
		"""Flag if the user has permission T (read-only). New since v7.4."""
		...

	@property
	def userid(self) -> str:
		"""The UserID of the EBICS account (read-only)."""
		...


class BusinessTransactionFormat:
	"""
	Business Transaction Format class

	Required for EBICS protocol version 3.0 (H005).

	With EBICS v3.0 you have to declare the file types you want to transfer. Please ask your bank what formats they provide. Instances of this class are used with EbicsClient.BTU(), EbicsClient.BTD() and all methods regarding the distributed signature.

	Examples:

	```python
	# SEPA Credit Transfer
	CCT = BusinessTransactionFormat(
									service='SCT',
									msg_name='pain.001',
	)

	# SEPA Direct Debit (Core)
	CDD = BusinessTransactionFormat(
									service='SDD',
									msg_name='pain.008',
									option='COR',
	)

	# SEPA Direct Debit (B2B)
	CDB = BusinessTransactionFormat(
									service='SDD',
									msg_name='pain.008',
									option='B2B',
	)

	# End of Period Statement (camt.053)
	C53 = BusinessTransactionFormat(
									service='EOP',
									msg_name='camt.053',
									scope='DE',
									container='ZIP',
	)
	```
	"""

	def __init__(
		self,
		service: str,
		msg_name: str,
		scope: str,
		option: str,
		container: str,
		version: str,
		variant: str,
		format: str,
	):
		"""Initializes the BTF instance.

		Parameters:
		* service – The service code name consisting of 3 alphanumeric characters [A-Z0-9] (eg. SCT, SDD, STM, EOP)
		* msg_name – The message name consisting of up to 10 alphanumeric characters [a-z0-9.] (eg. pain.001, pain.008, camt.053, mt940)
		* scope – Scope of service. Either an ISO-3166 ALPHA 2 country code or an issuer code of 3 alphanumeric characters [A-Z0-9].
		* option – The service option code consisting of 3-10 alphanumeric characters [A-Z0-9] (eg. COR, B2B)
		* container – Type of container consisting of 3 characters [A-Z] (eg. XML, ZIP)
		* version – Message version consisting of 2 numeric characters [0-9] (eg. 03)
		* variant – Message variant consisting of 3 numeric characters [0-9] (eg. 001)
		* format – Message format consisting of 1-4 alphanumeric characters [A-Z0-9] (eg. XML, JSON, PDF)
		"""
		...


class EbicsClient:
	"""Main EBICS client class."""

	def __init__(
		self,
		bank: EbicsBank,
		user: EbicsUser | list[EbicsUser],
		version: str = "H004",
	):
		"""
		Initializes the EBICS client instance.

		Parameters:
		* bank - An instance of EbicsBank.
		* user – An instance of EbicsUser. If you pass a list of users, a signature for each user is added to an upload request (new since v7.2). In this case the first user is the initiating one.
		* version – The EBICS protocol version (H003, H004 or H005). It is strongly recommended to use at least version H004 (2.5). When using version H003 (2.4) the client is responsible to generate the required order ids, which must be implemented by your application.
		"""
		...

	def BTD(
		self,
		btf: BusinessTransactionFormat,
		start: str | date | None = None,
		end: str | date | None = None,
		**params: Any,
	) -> bytes:
		"""
		Downloads data with EBICS protocol version 3.0 (H005).

		Parameters:
		* btf - Instance of BusinessTransactionFormat.
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* params - Additional keyword arguments, collected in params, are added as custom order parameters to the request.

		Returns:
		The requested file data.
		"""
		...

	def BTU(self, btf: BusinessTransactionFormat, data: bytes, **params: Any) -> str:
		"""
		Uploads data with EBICS protocol version 3.0 (H005).

		Parameters:
		* btf - Instance of BusinessTransactionFormat.
		* data - The data to upload.
		* params - Additional keyword arguments, collected in params, are added as custom order parameters to the request. Some banks in France require to upload a file in test mode the first time: TEST='TRUE'

		Returns:
		The order id (OrderID).
		"""
		...

	def C52(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> dict[str, Any] | bytes:
		"""
		Downloads Bank to Customer Account Reports (camt.52).

		Parameters:
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* parsed - Flag whether the received XML documents should be parsed and returned as structures of dictionaries or not.

		Returns:
		A dictionary of either raw XML documents or structures of dictionaries.
		"""
		...

	def C53(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> dict[str, Any] | bytes:
		"""
		Downloads Bank to Customer Statements (camt.53).

		Parameters:
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* parsed - Flag whether the received XML documents should be parsed and returned as structures of dictionaries or not.

		Returns:
		A dictionary of either raw XML documents or structures of dictionaries.
		"""
		...

	def C54(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> dict[str, Any] | bytes:
		"""
		Downloads Bank to Customer Debit Credit Notifications (camt.54).

		Parameters:
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* parsed - Flag whether the received XML documents should be parsed and returned as structures of dictionaries or not.

		Returns:
		A dictionary of either raw XML documents or structures of dictionaries.
		"""
		...

	def CCT(self, document: str | SEPACreditTransfer) -> str:
		"""
		Uploads a SEPA Credit Transfer document.

		Parameters:
		* document - The SEPA document to be uploaded either as a raw XML string or a fintech.sepa.SEPACreditTransfer object.

		Returns:
		The id of the uploaded order (OrderID).
		"""
		...

	def CCU(self, document: str | SEPACreditTransfer) -> str:
		"""
		Uploads a SEPA Credit Transfer document (Urgent Payments). New in v7.0.0.

		Parameters:
		* document - The SEPA document to be uploaded either as a raw XML string or a fintech.sepa.SEPACreditTransfer object.

		Returns:
		The id of the uploaded order (OrderID).
		"""
		...

	def CDB(self, document: str | "SEPADirectDebit") -> str:
		"""
		Uploads a SEPA Direct Debit document of type B2B.

		Parameters:
		* document - The SEPA document to be uploaded either as a raw XML string or a fintech.sepa.SEPADirectDebit object.

		Returns:
		The id of the uploaded order (OrderID).
		"""
		...

	def CDD(self, document: str | "SEPADirectDebit") -> str:
		"""
		Uploads a SEPA Direct Debit document of type CORE.

		Parameters:
		* document - The SEPA document to be uploaded either as a raw XML string or a fintech.sepa.SEPADirectDebit object.

		Returns:
		The id of the uploaded order (OrderID).
		"""
		...

	def CDZ(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> dict[str, Any] | bytes:
		"""
		Downloads Payment Status Report for Direct Debits.

		Parameters:
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* parsed - Flag whether the received XML documents should be parsed and returned as structures of dictionaries or not.

		Returns:
		A dictionary of either raw XML documents or structures of dictionaries.
		"""
		...

	def CIP(self, document: str | SEPACreditTransfer) -> str:
		"""Uploads a SEPA Credit Transfer document (Instant Payments).

		Parameters:
		* document - The SEPA document to be uploaded, either as a raw XML string or a fintech.sepa.SEPACreditTransfer object.

		Returns:
		The ID of the uploaded order (OrderID).
		"""
		...

	def CIZ(
		self, start: str | date = None, end: str | date = None, parsed: bool = False
	) -> dict:
		"""Downloads Payment Status Report for Credit Transfers (Instant Payments).

		Parameters:
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* parsed - Flag to determine whether the received XML documents should be parsed and returned as structures of dictionaries.

		Returns:
		A dictionary of either raw XML documents or structures of dictionaries.
		"""
		...

	def CRZ(
		self, start: str | date = None, end: str | date = None, parsed: bool = False
	) -> dict:
		"""Downloads Payment Status Report for Credit Transfers.

		Parameters:
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* parsed - Flag to determine whether the received XML documents should be parsed and returned as structures of dictionaries.

		Returns:
		A dictionary of either raw XML documents or structures of dictionaries.
		"""
		...

	def FDL(
		self,
		filetype: str,
		start: str | date = None,
		end: str | date = None,
		country: str = None,
		**params,
	) -> bytes:
		"""Downloads a file in arbitrary format. Not usable with EBICS 3.0 (H005).

		Parameters:
		* filetype - The requested file type.
		* start - The start date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested transactions. Can be a date object or an ISO8601 formatted string.
		* country - The country code (ISO-3166 ALPHA 2) if the specified file type is country-specific.
		* params - Additional keyword arguments to be added as custom order parameters to the request.

		Returns:
		The requested file data.
		"""
		...

	def FUL(self, filetype: str, data: bytes, country: str = None, **params) -> str:
		"""Uploads a file in arbitrary format. Not usable with EBICS 3.0 (H005).

		Parameters:
		* filetype - The file type to upload.
		* data - The file data to upload.
		* country - The country code (ISO-3166 ALPHA 2) if the specified file type is country-specific.
		* params - Additional keyword arguments to be added as custom order parameters to the request. Some banks in France require a test mode upload: TEST='TRUE'.

		Returns:
		The order ID (OrderID).
		"""
		...

	def H3K(self) -> str:
		"""Sends the public key of the electronic signature, the public authentication key, and the encryption key based on certificates. At least the signature key certificate must be signed by a certification authority (CA) or the bank itself.

		Returns:
		The assigned order ID.
		"""
		...

	def HAA(self, parsed: bool = False) -> dict:
		"""Downloads the available order types.

		Parameters:
		* parsed - Flag to determine whether the received XML document should be parsed and returned as a structure of dictionaries.

		Returns:
		Either the raw XML document or a structure of dictionaries.
		"""
		...

	def HAC(
		self, start: str | date = None, end: str | date = None, parsed: bool = False
	) -> dict:
		"""Downloads the customer usage report in XML format.

		Parameters:
		* start - The start date of requested processes. Can be a date object or an ISO8601 formatted string.
		* end - The end date of requested processes. Can be a date object or an ISO8601 formatted string.
		* parsed - Flag to determine whether the received XML document should be parsed and returned as a structure of dictionaries.

		Returns:
		Either the raw XML document or a structure of dictionaries.
		"""
		...

	def HCA(self, bitlength: int = 2048) -> str:
		"""Creates a new authentication and encryption key, transfers them to the bank, and updates the user key ring.

		Parameters:
		* bitlength - The bit length of the generated keys. The value must be between 1536 and 4096 (default is 2048).

		Returns:
		The assigned order ID.
		"""
		...

	def HCS(self, bitlength: int = 2048, keyversion: str | None = None) -> str:
		"""Creates a new signature, authentication, and encryption key, transfers them to the bank and updates the user key ring.

		It acts like a combination of EbicsClient.PUB() and EbicsClient.HCA().

		Parameters:
		* bitlength - The bit length of the generated keys. The value must be between 1536 and 4096 (default is 2048).
		* keyversion - The key version of the electronic signature. Supported versions are A005 (based on RSASSA-PKCS1-v1_5) and A006 (based on RSASSA-PSS). If not specified, the version of the current signature key is used.

		Returns: The assigned order id.
		"""
		...

	def HEV(self) -> dict:
		"""Returns a dictionary of supported protocol versions."""
		...

	def HIA(self) -> str:
		"""Sends the public authentication (X002) and encryption (E002) keys.

		Returns: The assigned order id.
		"""
		...

	def HKD(self, parsed: bool = False) -> str | dict:
		"""Downloads the customer properties and settings.

		Parameters:
		* parsed - Flag whether the received XML document should be parsed and returned as a structure of dictionaries or not.

		Returns: Either the raw XML document or a structure of dictionaries.
		"""
		...

	def HPB(self) -> str:
		"""Receives the public authentication (X002) and encryption (E002) keys from the bank.

		The keys are added to the key file and must be activated by calling the method EbicsBank.activate_keys().

		Returns: The string representation of the keys.
		"""
		...

	def HPD(self, parsed: bool = False) -> str | dict:
		"""Downloads the available bank parameters.

		Parameters:
		* parsed - Flag whether the received XML document should be parsed and returned as a structure of dictionaries or not.

		Returns: Either the raw XML document or a structure of dictionaries.
		"""
		...

	def HTD(self, parsed: bool = False) -> str | dict:
		"""Downloads the user properties and settings.

		Parameters:
		* parsed - Flag whether the received XML document should be parsed and returned as a structure of dictionaries or not.

		Returns: Either the raw XML document or a structure of dictionaries.
		"""
		...

	def HVD(
		self,
		orderid: str,
		ordertype: str | None = None,
		partnerid: str | None = None,
		parsed: bool = False,
	) -> str | dict:
		"""Downloads the signature status of a pending order.

		This method is part of the distributed signature.

		Parameters:
		* orderid - The id of the order in question.
		* ordertype - With EBICS protocol version H005, a BusinessTransactionFormat instance of the order. Otherwise, the type of the order in question. If not specified, the related BTF/order type is detected by calling the method EbicsClient.HVU().
		* partnerid - The partner id of the corresponding order. Defaults to the partner id of the current user.
		* parsed - Flag whether the received XML document should be parsed and returned as a structure of dictionaries or not.

		Returns: Either the raw XML document or a structure of dictionaries.
		"""
		...

	def HVE(
		self,
		orderid: str,
		ordertype: str | None = None,
		hash: str | None = None,
		partnerid: str | None = None,
	) -> None:
		"""Signs a pending order.

		This method is part of the distributed signature.

		Parameters:
		* orderid - The id of the order in question.
		* ordertype - With EBICS protocol version H005, a BusinessTransactionFormat instance of the order. Otherwise, the type of the order in question. If not specified, the related BTF/order type is detected by calling the method EbicsClient.HVZ().
		* hash - The base64 encoded hash of the order to be signed. If not specified, the corresponding hash is detected by calling the method EbicsClient.HVZ().
		* partnerid - The partner id of the corresponding order. Defaults to the partner id of the current user.
		"""
		...

	def HVS(
		self,
		orderid: str,
		ordertype: str | None = None,
		hash: str | None = None,
		partnerid: str | None = None,
	) -> None:
		"""Cancels a pending order.

		This method is part of the distributed signature.

		Parameters:
		* orderid - The id of the order in question.
		* ordertype - With EBICS protocol version H005, a BusinessTransactionFormat instance of the order. Otherwise, the type of the order in question. If not specified, the related BTF/order type is detected by calling the method EbicsClient.HVZ().
		* hash - The base64 encoded hash of the order to be canceled. If not specified, the corresponding hash is detected by calling the method EbicsClient.HVZ().
		* partnerid - The partner id of the corresponding order. Defaults to the partner id of the current user.
		"""
		...

	def HVT(
		self,
		orderid: str,
		ordertype: str | BusinessTransactionFormat | None = None,
		source: bool = False,
		limit: int = 100,
		offset: int = 0,
		partnerid: str | None = None,
		parsed: bool = False,
	) -> str | dict:
		"""Downloads the transaction details of a pending order as part of the distributed signature process.

		Parameters:
		* orderid – The id of the order in question.
		* ordertype – With EBICS protocol version H005, a BusinessTransactionFormat instance of the order; otherwise, the order type. If not specified, the related order type is detected by calling EbicsClient.HVU().
		* source – Boolean flag whether to return the original document of the order or just a summary of the corresponding transactions.
		* limit – The number of transactions returned. Applicable only if source evaluates to False.
		* offset – The offset of the first transaction to return. Applicable only if source evaluates to False.
		* partnerid – The partner id of the order, defaulting to the partner id of the current user.
		* parsed – Flag whether to parse the received XML document and return it as a dictionary structure or not.

		Returns: Either the raw XML document or a structure of dictionaries."""
		...

	def HVU(
		self,
		filter: list[str | BusinessTransactionFormat] | None = None,
		parsed: bool = False,
	) -> str | dict:
		"""Downloads pending orders waiting to be signed, as part of the distributed signature process.

		Parameters:
		* filter – With EBICS protocol version H005, an optional list of BusinessTransactionFormat instances to filter the result; otherwise, a list of order types for filtering.
		* parsed – Flag whether the received XML document should be parsed and returned as a structure of dictionaries or not.

		Returns: Either the raw XML document or a structure of dictionaries."""
		...

	def HVZ(
		self,
		filter: list[str | BusinessTransactionFormat] | None = None,
		parsed: bool = False,
	) -> str | dict:
		"""Downloads pending orders waiting to be signed. Combines the functionality of HVU() and HVD().

		Parameters:
		* filter – With EBICS protocol version H005, an optional list of BusinessTransactionFormat instances to filter the result; otherwise, a list of order types for filtering.
		* parsed – Flag whether the received XML document should be parsed and returned as a structure of dictionaries or not.

		Returns: Either the raw XML document or a structure of dictionaries."""
		...

	def INI(self) -> str:
		"""Sends the public key of the electronic signature.

		Returns: The assigned order id."""
		...

	def PTK(
		self, start: str | date | None = None, end: str | date | None = None
	) -> str:
		"""Downloads the customer usage report in text format.

		Parameters:
		* start – The start date of the requested processes (date object or ISO8601 formatted string).
		* end – The end date of the requested processes (date object or ISO8601 formatted string).

		Returns: The customer usage report."""
		...

	def PUB(self, bitlength: int = 2048, keyversion: str | None = None) -> str:
		"""Creates a new electronic signature key, transfers it to the bank, and updates the user key ring.

		Parameters:
		* bitlength – The bit length of the generated key (between 1536 and 4096, default 2048).
		* keyversion – The key version of the electronic signature. Supported versions: A005 (RSASSA-PKCS1-v1_5) and A006 (RSASSA-PSS). If not specified, the current signature key version is used.

		Returns: The assigned order id."""
		...

	def SPR(self) -> None:
		"""Locks the EBICS access of the current user."""
		...

	def STA(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> str | dict:
		"""Downloads the bank account statement in SWIFT format (MT940).

		Parameters:
		* start – The start date of the requested transactions (date object or ISO8601 formatted string).
		* end – The end date of the requested transactions (date object or ISO8601 formatted string).
		* parsed – Flag whether to parse the MT940 message and return it as a dictionary or not.

		Returns: Either the raw data of the MT940 SWIFT message or the parsed message as a dictionary."""
		...

	def VMK(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> str | dict:
		"""Downloads the interim transaction report in SWIFT format (MT942).

		Parameters:
		* start – The start date of the requested transactions (date object or ISO8601 formatted string).
		* end – The end date of the requested transactions (date object or ISO8601 formatted string).
		* parsed – Flag whether to parse the MT942 message and return it as a dictionary or not.

		Returns: Either the raw data of the MT942 SWIFT message or the parsed message as a dictionary."""
		...

	def XE2(self, document: str | SEPACreditTransfer) -> str:
		"""Uploads a SEPA Credit Transfer document (Switzerland).

		Parameters:
		* document – The SEPA document to upload, either as a raw XML string or a SEPACreditTransfer object.

		Returns: The id of the uploaded order (OrderID)."""
		...

	def Z01(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> dict:
		"""Downloads Payment Status Report (Switzerland, mixed).

		Parameters:
		* start – The start date of requested transactions (date object or ISO8601 formatted string).
		* end – The end date of requested transactions (date object or ISO8601 formatted string).
		* parsed – Flag whether the received XML documents should be parsed and returned as structures of dictionaries or not.

		Returns: A dictionary of either raw XML documents or structures of dictionaries."""
		...

	def Z53(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> dict:
		"""Downloads Bank to Customer Statements (Switzerland, camt.53).

		Parameters:
		* start – The start date of requested transactions (date object or ISO8601 formatted string).
		* end – The end date of requested transactions (date object or ISO8601 formatted string).
		* parsed – Flag whether the received XML documents should be parsed and returned as structures of dictionaries or not.

		Returns: A dictionary of either raw XML documents or structures of dictionaries."""
		...

	def Z54(
		self,
		start: str | date | None = None,
		end: str | date | None = None,
		parsed: bool = False,
	) -> dict:
		"""Downloads Bank Batch Statements ESR (Switzerland, C53F).

		Parameters:
		* start – The start date of requested transactions (date object or ISO8601 formatted string).
		* end – The end date of requested transactions (date object or ISO8601 formatted string).
		* parsed – Flag whether the received XML documents should be parsed and returned as structures of dictionaries or not.

		Returns: A dictionary of either raw XML documents or structures of dictionaries."""
		...

	@property
	def bank(self) -> "EbicsBank":
		"""Returns the EBICS bank (read-only)."""
		...

	@property
	def check_ssl_certificates(self) -> bool:
		"""Flag whether remote SSL certificates should be checked for validity (default: True)."""
		...

	def confirm_download(
		self, trans_id: str | None = None, success: bool = True
	) -> None:
		"""Confirms the receipt of previously executed downloads.

		Parameters:
		* trans_id – The transaction id of the download (see last_trans_id). If not specified, all previously unconfirmed downloads are confirmed.
		* success – Informs the EBICS server whether the downloaded data was successfully processed or not."""
		...

	def download(
		self,
		order_type: str,
		start: str | date | None = None,
		end: str | date | None = None,
		params: list | dict | None = None,
	):
		"""Performs an arbitrary EBICS download request.

		Parameters:
		* order_type - The id of the intended order type.
		* start - The start date of requested documents. Can be a date object or an ISO8601 formatted string. Not allowed with all order types.
		* end - The end date of requested documents. Can be a date object or an ISO8601 formatted string. Not allowed with all order types.
		* params - A list or dictionary of parameters that are added to the EBICS request. Cannot be combined with a date range specified by start and end.

		Returns: The downloaded data. The returned transaction id is stored in the attribute last_trans_id.
		"""
		...

	@property
	def last_trans_id(self) -> str:
		"""This attribute stores the transaction id of the last download process (read-only)."""
		...

	def listen(self, filter: list[str] | None = None) -> None:
		"""Connects to the EBICS websocket server and listens for new incoming messages. This is a blocking service.

		Parameters:
		* filter - An optional list of order types or BTF message names (BusinessTransactionFormat.msg_name) that will be processed.Other data types are skipped.
		"""
		...

	@property
	def suppress_no_data_error(self) -> bool:
		"""Flag whether to suppress exceptions if no download data is available or not.

		The default value is False. If set to True, download methods return None in the case that no download data is available.
		"""
		...

	@suppress_no_data_error.setter
	def suppress_no_data_error(self, value: bool) -> None:
		"""Sets the flag to suppress exceptions if no download data is available.

		Parameters:
		* value - Boolean value to set suppress_no_data_error flag.
		"""
		...

	@property
	def timeout(self) -> int:
		"""The timeout in seconds for EBICS connections (default: 30)."""
		...

	@timeout.setter
	def timeout(self, value: int) -> None:
		"""Sets the timeout in seconds for EBICS connections.

		Parameters:
		* value - The timeout value in seconds.
		"""
		...

	def upload(
		self,
		order_type: str,
		data: str,
		params: list | dict | None = None,
		prehashed: bool = False,
	) -> str:
		"""Performs an arbitrary EBICS upload request.

		Parameters:
		* order_type - The id of the intended order type.
		* data - The data to be uploaded.
		* params - A list or dictionary of parameters that are added to the EBICS request.
		* prehashed - Flag whether the data contains a prehashed value or not.

		Returns: The id of the uploaded order, if applicable.
		"""
		...

	@property
	def user(self) -> EbicsUser | list[EbicsUser]:
		"""The EBICS user (read-only)."""
		...

	@property
	def version(self) -> str:
		"""The EBICS protocol version (read-only)."""
		...

	@property
	def websocket(self):
		"""The websocket instance if running (read-only)."""
		...


class CAMTDocument:
	"""The CAMTDocument class is used to parse CAMT52, CAMT53 or CAMT54 documents.
	An instance can be treated as an iterable over its transactions, each represented as an instance of type SEPATransaction.

	Note: If orders were submitted in batch mode, there are three methods to resolve the underlying transactions.
	Either (A) directly within the CAMT52/CAMT53 document, (B) within a separate CAMT54 document or
	(C) by a reference to the originally transferred PAIN message. The applied method depends on the bank (method B is most commonly used).
	"""

	def __init__(self, xml: str, camt54: str | list[str] = None):
		"""Initializes the CAMTDocument instance.

		Parameters:
		* xml - The XML string of a CAMT document to be parsed (either CAMT52, CAMT53 or CAMT54).
		* camt54 - In case xml is a CAMT52 or CAMT53 document, an additional CAMT54 document or a sequence of such documents can be passed, which are automatically merged with the corresponding batch transactions.
		"""
		...
	
	def __iter__(self) -> Iterator[SEPATransaction]:
		"""Returns an iterator over the transactions."""
		...

	@property
	def balance_close(self) -> "Amount":
		"""The closing balance of type Amount (read-only)."""
		...

	@property
	def balance_open(self) -> "Amount":
		"""The opening balance of type Amount (read-only)."""
		...

	@property
	def bic(self) -> str:
		"""The local BIC (read-only)."""
		...

	@property
	def created(self) -> str:
		"""The date of creation (read-only)."""
		...

	@property
	def currency(self) -> str:
		"""The currency of the account (read-only)."""
		...

	@property
	def date_from(self) -> str:
		"""The start date (read-only)."""
		...

	@property
	def date_to(self) -> str:
		"""The end date (read-only)."""
		...

	@property
	def iban(self) -> str:
		"""The local IBAN (read-only)."""
		...

	@property
	def info(self) -> str:
		"""Some info text about the document (read-only)."""
		...

	@property
	def message_id(self) -> str:
		"""The message id (read-only)."""
		...

	@property
	def name(self) -> str:
		"""The name of the account holder (read-only)."""
		...

	@property
	def reference_id(self) -> str:
		"""A unique reference number (read-only)."""
		...

	@property
	def sequence_id(self) -> str:
		"""The statement sequence number (read-only)."""
		...

	@property
	def type(self) -> str:
		"""The CAMT type, e.g. camt.053.001.02 (read-only)."""
		...
