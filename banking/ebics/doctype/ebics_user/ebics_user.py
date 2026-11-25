# Copyright (c) 2024, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form
from frappe.utils.data import comma_and, getdate
from frappe.utils.synchronization import filelock
from requests import Response

from banking.ebics.utils import get_ebics_manager, get_protocol_versions, sync_ebics_transactions
from banking.klarna_kosma_integration.admin import Admin


class EBICSUser(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bank: DF.Link | None
		bank_keys_activated: DF.Check
		country: DF.Link | None
		download_batch_transactions: DF.Check
		full_name: DF.Data | None
		ini_sent: DF.Check
		initialized: DF.Check
		intraday_sync: DF.Check
		keyring: DF.Code | None
		needs_certificates: DF.Check
		organization_name: DF.Data | None
		partner_id: DF.Data | None
		passphrase: DF.Password | None
		protocol_version: DF.Literal["H004", "H005"]
		split_batch_transactions: DF.Check
		start_date: DF.Date | None
		user_id: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if self.partner_id:
			self.partner_id = self.partner_id.strip()

		if self.user_id:
			self.user_id = self.user_id.strip()

		if any(self.has_value_changed(field) for field in ("bank", "partner_id", "user_id")):
			# The bank received INI for the old IDs, so the new IDs need INI as well.
			self.ini_sent = 0

		if self.country:
			self.validate_country_code()

		if self.bank:
			self.validate_bank()

		self.validate_protocol_version()

	def on_update(self):
		previous = self.get_doc_before_save()
		if not previous or get_ebics_ids(previous) == get_ebics_ids(self):
			self.register_user()
			return

		# Remove first, so that a plan without a free slot can register the new IDs.
		previous.remove_user()
		try:
			self.register_user()
		except Exception:
			# The save rolls back and keeps the old IDs, so register them again.
			previous.register_user()
			raise

	def on_trash(self):
		self.remove_user()

	def register_user(self, host_id: str | None = None):
		"""Idempotent method to register the user with the admin backend.

		Uses the host ID of the bank, unless `host_id` is given.
		"""
		if not all(get_ebics_ids(self)):
			return

		host_id = host_id or frappe.db.get_value("Bank", self.bank, "ebics_host_id")
		response = Admin().request.register_ebics_user(host_id, self.partner_id, self.user_id)
		self.throw_on_admin_error(response, _("Failed to register EBICS User."))

	def remove_user(self, host_id: str | None = None):
		"""Idempotent method to remove the user from the admin backend.

		Uses the host ID of the bank, unless `host_id` is given.
		"""
		if not all(get_ebics_ids(self)):
			return

		host_id = host_id or frappe.db.get_value("Bank", self.bank, "ebics_host_id")
		response = Admin().request.register_ebics_user(host_id, self.partner_id, self.user_id, remove=True)
		self.throw_on_admin_error(response, _("Failed to remove EBICS user registration."))

	def move_registration(self, old_host_id: str, new_host_id: str):
		"""Register the user under the new host ID of the bank instead of the old one."""
		# Remove first, so that a plan without a free slot can register the new host ID.
		self.remove_user(old_host_id)
		try:
			self.register_user(new_host_id)
		except Exception:
			self.register_user(old_host_id)
			raise

	def throw_on_admin_error(self, response: Response, title: str):
		"""Throw the reason from the admin backend if the response is not 2xx."""
		is_success = 200 <= response.status_code < 300
		if is_success:
			return

		try:
			message = response.json().get("message")
		except ValueError:  # Gateway errors have no JSON body
			message = None

		message = message or _("The license server responded with status code {0}.").format(
			response.status_code
		)
		frappe.log_error(
			title=title,
			message=message,
			reference_doctype="EBICS User",
			reference_name=self.name,
		)
		frappe.throw(title=title, msg=message)

	def validate_country_code(self):
		country_code = self.get_country_code()
		if not country_code or len(country_code) != 2:
			frappe.throw(
				_("Please add a two-letter country code to country {0}").format(
					get_link_to_form("Country", self.country)
				)
			)

	def validate_bank(self):
		host_id, url = frappe.db.get_value("Bank", self.bank, ["ebics_host_id", "ebics_url"])
		if not host_id or not url:
			frappe.throw(
				_("Please add EBICS Host ID and URL to bank {0}").format(get_link_to_form("Bank", self.bank))
			)

		try:
			supported_protocol_versions = get_protocol_versions(host_id, url)
		except Exception:
			frappe.msgprint(
				_(
					"The bank did not answer. Please check the EBICS URL and EBICS Host ID of bank {0}."
				).format(get_link_to_form("Bank", self.bank)),
				indicator="orange",
			)
			return

		if supported_protocol_versions and self.protocol_version not in supported_protocol_versions:
			frappe.throw(
				_("You selected protocol version {0}, but the bank {1} only supports {2}.").format(
					self.protocol_version,
					get_link_to_form("Bank", self.bank),
					comma_and(supported_protocol_versions.keys()),
				)
			)

	def validate_protocol_version(self):
		if self.protocol_version == "H005" and not self.needs_certificates:
			frappe.throw(
				_("To use protocol version H005, please activate the checkbox 'Needs Certificates'.")
			)

	def get_country_code(self) -> str | None:
		"""Return the ISO-3166 ALPHA 2 country code."""
		code = frappe.db.get_value("Country", self.country, "code")
		return code.upper() if code else None

	def get_passphrase(self) -> str | None:
		"""Return the passphrase if it is set and valid, otherwise None."""
		if not self.passphrase:
			return None

		try:
			passphrase = self.get_password("passphrase")
		except (frappe.exceptions.AuthenticationError, frappe.exceptions.ValidationError):
			return None

		return passphrase or None

	def attach_ini_letter(self, pdf_bytes: bytes):
		file = frappe.new_doc("File")
		file.file_name = f"ini_letter_{self.name}.pdf"
		file.attached_to_doctype = self.doctype
		file.attached_to_name = self.name
		file.is_private = 1
		file.content = pdf_bytes
		file.save()

	def store_keyring(self, keys: dict):
		self.db_set("keyring", json.dumps(keys, indent=2))

	def get_keyring(self) -> dict:
		return json.loads(self.keyring) if self.keyring else {}


def get_ebics_ids(user: EBICSUser) -> tuple:
	"""Return the combination of IDs that is registered with the admin backend."""
	return user.bank, user.partner_id, user.user_id


def on_doctype_update():
	frappe.db.add_unique("EBICS User", ["bank", "partner_id", "user_id"], constraint_name="unique_ebics_user")


@frappe.whitelist(methods=["POST"])
def initialize(ebics_user: str, passphrase: str, signature_passphrase: str, store_passphrase: int):
	ensure_ebics_is_enabled()

	# The steps below commit, so a failed request keeps its keys. A second request must not
	# create other keys at the same time. `for_update` reads the latest committed values.
	with filelock(f"initialize_ebics_user_{ebics_user}", timeout=0):
		user = frappe.get_doc("EBICS User", ebics_user, for_update=True)
		user.check_permission("write")

		if store_passphrase:
			user.passphrase = passphrase
			user.save()

		try:
			manager = get_ebics_manager(
				ebics_user=user, passphrase=passphrase, sig_passphrase=signature_passphrase
			)
		except ValueError as e:
			# Keys from an earlier try are encrypted with the passphrases of that try.
			if "wrong passphrase" not in str(e):
				raise

			message = _(
				"This EBICS User already has keys from an earlier try. Please enter the same passphrases as in that try. If you forgot them, delete this EBICS User and create a new one."
			)
			if user.ini_sent:
				message += " " + _(
					"The bank already received the old keys, so it may reject the new ones. In that case, ask your bank to reset the user."
				)

			frappe.throw(message, title=_("Wrong Passphrase"))

		# After INI, the bank has the signature key. Keep the keys and do not send INI again.
		# Some banks reject a second INI. Others replace the keys until they process the INI letter.
		# Skipping INI works with both, because the keys stay the same.
		if not user.ini_sent:
			try:
				manager.create_user_keys()
			except RuntimeError as e:
				if e.args[0] != "keys already present":
					raise e

			if user.needs_certificates:
				manager.create_user_certificates(user.full_name, user.organization_name)

			frappe.db.commit()  # nosemgrep

		with explain_ebics_errors(user):
			if not user.ini_sent:
				manager.send_signature_key()
				user.db_set("ini_sent", 1, commit=True)

			manager.send_authentication_keys()

		bank_name = frappe.db.get_value("Bank", user.bank, "bank_name")
		language = frappe.local.lang if frappe.local.lang in ("de", "fr") else "en"
		ini_bytes = manager.create_ini_letter(bank_name, language=language)
		user.attach_ini_letter(ini_bytes)
		user.db_set("initialized", 1)


@frappe.whitelist(methods=["POST"])
def download_bank_keys(ebics_user: str, passphrase: str | None = None):
	ensure_ebics_is_enabled()

	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	manager = get_ebics_manager(user, passphrase=passphrase)

	with explain_ebics_errors(user):
		return manager.download_bank_keys()


@frappe.whitelist(methods=["POST"])
def confirm_bank_keys(ebics_user: str, passphrase: str | None = None):
	ensure_ebics_is_enabled()

	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	manager = get_ebics_manager(user, passphrase=passphrase)
	manager.activate_bank_keys()
	user.db_set("bank_keys_activated", 1)


@frappe.whitelist(methods=["POST"])
def download_bank_statements(
	ebics_user: str,
	from_date: str | None = None,
	to_date: str | None = None,
	passphrase: str | None = None,
):
	ensure_ebics_is_enabled()

	frappe.has_permission("Bank Transaction", "create", throw=True)

	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("read")

	frappe.enqueue(
		sync_ebics_transactions,
		requested_by="User",
		ebics_user=ebics_user,
		start_date=from_date,
		end_date=to_date,
		passphrase=passphrase,
		intraday=getdate(from_date) == getdate(),
		now=frappe.conf.developer_mode,
	)


@frappe.whitelist(methods=["PUT"])
def change_protocol_version(ebics_user: str, protocol_version: str, passphrase: str | None = None):
	ensure_ebics_is_enabled()

	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	user.protocol_version = protocol_version
	user.bank_keys_activated = 0

	if protocol_version == "H005":
		user.needs_certificates = 1

	user.save()

	if user.needs_certificates:
		manager = get_ebics_manager(user, passphrase=passphrase)
		manager.create_user_certificates(user.full_name, user.organization_name)


def ensure_ebics_is_enabled():
	if not frappe.db.get_single_value("Banking Settings", "enabled"):
		frappe.throw(
			_("Please activate the checkbox 'Enabled' in the {0}.").format(
				get_link_to_form("Banking Settings", "Banking Settings")
			)
		)

	if not frappe.db.get_single_value("Banking Settings", "enable_ebics"):
		frappe.throw(
			_("Please activate the checkbox 'Enable EBICS' in the {0}.").format(
				get_link_to_form("Banking Settings", "Banking Settings")
			)
		)


@contextmanager
def explain_ebics_errors(user: EBICSUser):
	"""Turn common EBICS errors from the bank into messages that tell the user what to check."""
	from fintech.ebics import EbicsTechnicalError

	try:
		yield
	except EbicsTechnicalError as error:
		messages = {
			EbicsTechnicalError.EBICS_INVALID_USER_OR_USER_STATE: _(
				"The bank does not accept this EBICS User in its current state. Please check the Partner ID and the User ID. If both are correct, ask your bank about the state of this user. For example, the bank may already have keys from an earlier initialization."
			),
			EbicsTechnicalError.EBICS_USER_UNKNOWN: _(
				"The bank does not know this EBICS User. Please check the Partner ID and the User ID."
			),
			EbicsTechnicalError.EBICS_INVALID_USER_STATE: _(
				"The bank has not activated this EBICS User yet. Please wait until your bank has processed the INI letter."
			),
			EbicsTechnicalError.EBICS_INVALID_HOST_ID: _(
				"The bank does not know this EBICS Host ID. Please check the EBICS Host ID of bank {0}."
			).format(get_link_to_form("Bank", user.bank)),
			EbicsTechnicalError.EBICS_AUTHENTICATION_FAILED: _(
				"The bank could not verify the keys of this EBICS User. The keys in this system may not match the keys at the bank. Please contact your bank."
			),
		}
		message = messages.get(error.code)
		if not message:
			raise

		bank_response = _("Bank response: {0}").format(str(error))
		frappe.throw(f"{message}<br><br>{bank_response}", title=_("EBICS Error"))
