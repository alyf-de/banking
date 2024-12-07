import fintech
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from typing import Iterator, Callable
	from banking.ebics.types import (
		EbicsKeyRing,
		EbicsUser,
		EbicsBank,
		EbicsClient,
		CAMTDocument,
	)


class EBICSManager:
	__slots__ = ["keyring", "user", "bank"]

	def __init__(
		self,
		license_name: str,
		license_key: str,
	):
		try:
			fintech.register(
				name=license_name,
				keycode=license_key,
			)
		except RuntimeError as e:
			if e.args[0] != "'register' can be called only once":
				raise e

	def set_keyring(
		self, keys: dict, save_to_db: "Callable", sig_passphrase: str, passphrase: str | None
	):
		from fintech.ebics import EbicsKeyRing

		class CustomKeyRing(EbicsKeyRing):
			def _write(self, keydict):
				save_to_db(keydict)

		self.keyring: "EbicsKeyRing" = CustomKeyRing(
			keys=keys,
			passphrase=passphrase,
			sig_passphrase=sig_passphrase,
		)

	def set_user(self, partner_id: str, user_id: str):
		from fintech.ebics import EbicsUser

		self.user: "EbicsUser" = EbicsUser(
			keyring=self.keyring, partnerid=partner_id, userid=user_id, transport_only=True
		)

	def set_bank(self, host_id: str, url: str):
		from fintech.ebics import EbicsBank

		self.bank: "EbicsBank" = EbicsBank(keyring=self.keyring, hostid=host_id, url=url)

	def create_user_keys(self):
		self.user.create_keys(keyversion="A005", bitlength=2048)

	def create_user_certificates(
		self, user_name: str, organization_name: str, country_code: str
	):
		self.user.create_certificates(
			commonName=user_name,
			organizationName=organization_name,
			countryName=country_code,
		)

	def get_client(self) -> "EbicsClient":
		from fintech.ebics import EbicsClient

		return EbicsClient(self.bank, self.user)

	def send_keys_to_bank(self):
		client = self.get_client()
		# Send the public electronic signature key to the bank.
		client.INI()
		# Send the public authentication and encryption keys to the bank.
		client.HIA()

	def create_ini_letter(self, bank_name: str, language: str | None = None) -> bytes:
		"""Return the PDF data as byte string."""
		return self.user.create_ini_letter(
			bankname=bank_name,
			lang=language,
		)

	def download_bank_keys(self):
		client = self.get_client()
		return client.HPB()

	def activate_bank_keys(self) -> None:
		self.bank.activate_keys()

	def get_permitted_order_types(self, level: str = "T") -> list[str]:
		"""Return a list of individual order types for the given (or unspecified) authorisation level."""
		client = self.get_client()
		user_data = client.HTD(parsed=True)
		permissions = (
			user_data.get("HTDResponseOrderData", {}).get("UserInfo", {}).get("Permission", [])
		)

		# Collect all order types for the specified level
		level_perms = []
		for permission in permissions:
			if permission.get("@AuthorisationLevel", level) == level:
				order_types = permission.get("OrderTypes")
				if isinstance(order_types, str):
					# Split if it's a space-separated string
					level_perms.extend(order_types.split())

		return level_perms

	def download_bank_statements(
		self, start_date: str | None = None, end_date: str | None = None
	) -> "Iterator[CAMTDocument]":
		"""Yield an iterator over CAMTDocument objects for the given date range."""
		from fintech.sepa import CAMTDocument

		client = self.get_client()
		permitted_types = self.get_permitted_order_types()

		try:
			camt53 = client.C53(start_date, end_date)
		except fintech.ebics.EbicsNoDataAvailable:
			return

		camt54 = client.C54(start_date, end_date) if "C54" in permitted_types else None

		for name in sorted(camt53):
			yield CAMTDocument(xml=camt53[name], camt54=camt54)

		client.confirm_download(success=True)
