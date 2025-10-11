from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from collections.abc import Callable

	from fintech.ebics import (
		EbicsClient,
	)


@dataclass
class EbicsRequest:
	"""Parameters for an EBICS download request."""

	order_type: str  # e.g., "C52", "Z53", "C54"
	camt_msg: str  # e.g., "camt.052", "camt.053", "camt.054"
	service: str  # "STM" for statements, "EOP" for end-of-period
	start_date: str | None = None
	end_date: str | None = None


class EBICSManager:
	__slots__ = ["bank", "country_code", "keyring", "protocol_version", "user"]

	def __init__(self, protocol_version: str | None = None, country_code: str | None = None):
		self.protocol_version = protocol_version or "H004"
		self.country_code = country_code

	def set_keyring(self, keys: dict, save_to_db: "Callable", passphrase: str, sig_passphrase: str | None):
		from fintech.ebics import EbicsKeyRing

		class CustomKeyRing(EbicsKeyRing):
			def _write(self, keydict):
				save_to_db(keydict)

		self.keyring = CustomKeyRing(
			keys=keys,
			passphrase=passphrase,
			sig_passphrase=sig_passphrase,
		)

	def set_user(self, partner_id: str, user_id: str):
		from fintech.ebics import EbicsUser

		self.user = EbicsUser(keyring=self.keyring, partnerid=partner_id, userid=user_id, transport_only=True)

	def set_bank(self, host_id: str, url: str):
		from fintech.ebics import EbicsBank

		self.bank = EbicsBank(keyring=self.keyring, hostid=host_id, url=url)

	def create_user_keys(self):
		self.user.create_keys(keyversion="A005", bitlength=2048)

	def create_user_certificates(self, user_name: str, organization_name: str):
		self.user.create_certificates(
			commonName=user_name,
			organizationName=organization_name,
			countryName=self.country_code,
		)

	def get_client(self) -> "EbicsClient":
		from fintech.ebics import EbicsClient

		return EbicsClient(self.bank, self.user, self.protocol_version)

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
		permissions = user_data.get("HTDResponseOrderData", {}).get("UserInfo", {}).get("Permission", [])

		# Collect all order types for the specified level
		level_perms = []
		for permission in permissions:
			if permission.get("@AuthorisationLevel", level) == level:
				order_types = permission.get("OrderTypes")
				if isinstance(order_types, str):
					# Split if it's a space-separated string
					level_perms.extend(order_types.split())

		return level_perms

	def download(self, request: EbicsRequest) -> dict:
		"""Execute an EBICS download request.

		Args:
			request: EbicsRequest containing order type and parameters

		Returns:
			dict: The downloaded files.
		"""
		client = self.get_client()

		if client.version != "H005":
			return client.download(request.order_type, request.start_date, request.end_date)

		from fintech.ebics import BusinessTransactionFormat

		btf = BusinessTransactionFormat(
			service=request.service,
			msg_name=request.camt_msg,
			scope=self.country_code,
			container="ZIP",
		)
		return client.BTD(btf, request.start_date, request.end_date)

	def confirm_download(self, success: bool = True):
		"""Confirm the receipt of previously executed downloads.

		Args:
			success: Whether the download was successfully processed.
		"""
		client = self.get_client()
		return client.confirm_download(success=success)
