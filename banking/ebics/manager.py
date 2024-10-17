import fintech


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

	def set_keyring(self, keyring_path: str, keyring_passphrase: str):
		from fintech.ebics import EbicsKeyRing

		self.keyring = EbicsKeyRing(
			keys=keyring_path,
			passphrase=keyring_passphrase,
		)

	def set_user(self, partner_id: str, user_id: str):
		from fintech.ebics import EbicsUser

		self.user = EbicsUser(
			keyring=self.keyring, partnerid=partner_id, userid=user_id, transport_only=True
		)

	def set_bank(self, host_id: str, url: str):
		from fintech.ebics import EbicsBank

		self.bank = EbicsBank(keyring=self.keyring, hostid=host_id, url=url)

	def create_user_keys(self):
		self.user.create_keys(keyversion="A005", bitlength=2048)

	def create_user_certificates(self, user_name: str, organization_name: str, country_code: str):
		self.user.create_certificates(
			commonName=user_name,
			organizationName=organization_name,
			countryName=country_code,
		)

	def get_client(self):
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

	def download_bank_statements(self, start_date: str | None = None, end_date: str | None = None):
		"""Yield an iterator over CAMTDocument objects for the given date range."""
		from fintech.sepa import CAMTDocument

		client = self.get_client()
		camt53 = client.C53(start_date, end_date)
		try:
			camt54 = client.C54(start_date, end_date)
		except fintech.ebics.EbicsTechnicalError as e:
			camt54 = None

		for name in sorted(camt53):
			yield CAMTDocument(xml=camt53[name], camt54=camt54)

		client.confirm_download(success=True)
