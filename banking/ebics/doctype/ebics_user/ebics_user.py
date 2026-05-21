# Copyright (c) 2024, ALYF GmbH and contributors
# For license information, please see license.txt
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form
from frappe.utils.data import comma_and, getdate
from requests import HTTPError

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
		company: DF.Link | None
		country: DF.Link | None
		download_batch_transactions: DF.Check
		full_name: DF.Data | None
		initialized: DF.Check
		intraday_sync: DF.Check
		keyring: DF.Code | None
		needs_certificates: DF.Check
		partner_id: DF.Data | None
		passphrase: DF.Password | None
		protocol_version: DF.Literal["H004", "H005"]
		split_batch_transactions: DF.Check
		start_date: DF.Date | None
		user_id: DF.Data | None

	# end: auto-generated types
	def validate(self):
		if self.country:
			self.validate_country_code()

		if self.bank:
			self.validate_bank()

		self.validate_protocol_version()

	def before_insert(self):
		self.register_user()

	def on_update(self):
		self.register_user()

	def on_trash(self):
		self.remove_user()

	def register_user(self):
		"""Indempotent method to register the user with the admin backend."""
		host_id = frappe.db.get_value("Bank", self.bank, "ebics_host_id")
		try:
			r = Admin().request.register_ebics_user(host_id, self.partner_id, self.user_id)
			r.raise_for_status()
		except HTTPError as e:
			if e.response.status_code == 402:
				# User already exists for this customer
				return
			elif e.response.status_code == 403:
				title = _("Banking Error")
				msg = _("EBICS User limit exceeded.")
				frappe.log_error(
					title=_("Banking Error"),
					message=msg,
					reference_doctype="EBICS User",
					reference_name=self.name,
				)
				frappe.throw(title=title, msg=msg)
			elif e.response.status_code == 409:
				title = _("Banking Error")
				msg = _("User ID not available.")
				frappe.log_error(
					title=_("Banking Error"),
					message=msg,
					reference_doctype="EBICS User",
					reference_name=self.name,
				)
				frappe.throw(title=title, msg=msg)

	def remove_user(self):
		"""Indempotent method to remove the user from the admin backend."""
		host_id = frappe.db.get_value("Bank", self.bank, "ebics_host_id")
		try:
			r = Admin().request.register_ebics_user(host_id, self.partner_id, self.user_id, remove=True)
			r.raise_for_status()
		except HTTPError:
			title = _("Failed to remove EBICS user registration.")
			frappe.log_error(
				title=title,
				reference_doctype="EBICS User",
				reference_name=self.name,
			)
			frappe.throw(title)

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
			supported_protocol_versions = {}

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
		except frappe.exceptions.AuthenticationError, frappe.exceptions.ValidationError:
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


def on_doctype_update():
	frappe.db.add_unique("EBICS User", ["bank", "partner_id", "user_id"], constraint_name="unique_ebics_user")


@frappe.whitelist(methods=["POST"])
def initialize(ebics_user: str, passphrase: str, signature_passphrase: str, store_passphrase: int):
	ensure_ebics_is_enabled()

	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	if store_passphrase:
		user.passphrase = passphrase
		user.save()

	manager = get_ebics_manager(ebics_user=user, passphrase=passphrase, sig_passphrase=signature_passphrase)

	try:
		manager.create_user_keys()
	except RuntimeError as e:
		if e.args[0] != "keys already present":
			raise e

	if user.needs_certificates:
		manager.create_user_certificates(user.full_name, user.company)

	manager.send_keys_to_bank()

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


@frappe.whitelist(methods=["POST"])
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
		manager.create_user_certificates(user.full_name, user.company)


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
