# Copyright (c) 2024, ALYF GmbH and contributors
# For license information, please see license.txt
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form
from frappe.utils.data import getdate

from banking.ebics.utils import get_ebics_manager, sync_ebics_transactions
from banking.klarna_kosma_integration.admin import Admin
from requests import HTTPError


class EBICSUser(Document):
	def validate(self):
		if self.country:
			self.validate_country_code()

		if self.bank:
			self.validate_bank()

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
			r = Admin().request.remove_ebics_user(host_id, self.partner_id, self.user_id)
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
		country_code = frappe.db.get_value("Country", self.country, "code")
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
				_("Please add EBICS Host ID and URL to bank {0}").format(
					get_link_to_form("Bank", self.bank)
				)
			)

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
	frappe.db.add_unique(
		"EBICS User", ["bank", "partner_id", "user_id"], constraint_name="unique_ebics_user"
	)


@frappe.whitelist()
def initialize(
	ebics_user: str, passphrase: str, signature_passphrase: str, store_passphrase: int
):
	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	if store_passphrase:
		user.passphrase = passphrase
		user.save()

	manager = get_ebics_manager(
		ebics_user=user, passphrase=passphrase, sig_passphrase=signature_passphrase
	)

	try:
		manager.create_user_keys()
	except RuntimeError as e:
		if e.args[0] != "keys already present":
			raise e

	if user.needs_certificates:
		country_code = frappe.db.get_value("Country", user.country, "code")
		manager.create_user_certificates(user.full_name, user.company, country_code.upper())

	manager.send_keys_to_bank()

	bank_name = frappe.db.get_value("Bank", user.bank, "bank_name")
	ini_bytes = manager.create_ini_letter(bank_name, language=frappe.local.lang)
	user.attach_ini_letter(ini_bytes)
	user.db_set("initialized", 1)


@frappe.whitelist()
def download_bank_keys(ebics_user: str, passphrase: str | None = None):
	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	manager = get_ebics_manager(user, passphrase=passphrase)

	return manager.download_bank_keys()


@frappe.whitelist()
def confirm_bank_keys(ebics_user: str, passphrase: str | None = None):
	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("write")

	manager = get_ebics_manager(user, passphrase=passphrase)
	manager.activate_bank_keys()
	user.db_set("bank_keys_activated", 1)


@frappe.whitelist()
def download_bank_statements(
	ebics_user: str,
	from_date: str | None = None,
	to_date: str | None = None,
	passphrase: str | None = None,
):
	frappe.has_permission("Bank Transaction", "create", throw=True)

	user = frappe.get_doc("EBICS User", ebics_user)
	user.check_permission("read")

	frappe.enqueue(
		sync_ebics_transactions,
		ebics_user=ebics_user,
		start_date=from_date,
		end_date=to_date,
		passphrase=passphrase,
		intraday=getdate(from_date) == getdate(),
		now=frappe.conf.developer_mode,
	)
