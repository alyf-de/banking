# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt
import contextlib
from enum import Enum
from typing import TYPE_CHECKING

import frappe
import kontocheck
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import now_datetime

from banking.ebics.utils import get_ebics_manager, register_fintech

if TYPE_CHECKING:
	from fintech.sepa import SEPACreditTransfer


class PaymentOrderStatus(str, Enum):
	"""
	Single source of truth for payment order status values.
	Used to determine select field options and communicate changes via hooks.
	The patch to recreate custom fields must run if this enum changes.
	"""

	CANCELLED = ""  # empty must come first, for select option order
	DRAFT = "Draft"
	APPROVED = "Approved"
	TRANSMITTED = "Transmitted"


class SEPAPaymentOrder(Document):
	def before_validate(self):
		kontocheck.lut_load()

		for payment in self.payments:
			if payment.iban and payment.iban.startswith("DE"):
				if not payment.swift_number:
					with contextlib.suppress(Exception):
						payment.swift_number = kontocheck.get_bic(payment.iban)
				if not payment.bank_name and payment.swift_number:
					with contextlib.suppress(Exception):
						payment.bank_name = kontocheck.scl_get_bankname(payment.swift_number)

	def validate(self):
		self.validate_ibans()
		self.validate_account_currency()

	def validate_ibans(self):
		kontocheck.lut_load()

		if not kontocheck.check_iban(self.iban):
			frappe.throw(_("IBAN {0} is invalid.").format(self.iban))

		for payment in self.payments:
			if not kontocheck.check_iban(payment.iban):
				frappe.throw(_("Row {0}: IBAN {1} is invalid.").format(payment.idx, payment.iban))

	def validate_account_currency(self):
		"""Validate that each payment currency is the same as the account currency."""
		account_name = frappe.db.get_value("Bank Account", self.bank_account, "account")
		account_currency = frappe.db.get_value("Account", account_name, "account_currency")
		for payment in self.payments:
			if payment.currency != account_currency:
				frappe.throw(
					_("Row {0}: Currency {1} does not match bank account currency {2}.").format(
						payment.idx, payment.currency, account_currency
					)
				)

	def after_insert(self):
		self.notify_reference_docs(status=PaymentOrderStatus.DRAFT)

	def on_submit(self):
		self.notify_reference_docs(status=PaymentOrderStatus.APPROVED)

	def on_update_after_submit(self):
		if self.transmission_datetime:
			self.notify_reference_docs(status=PaymentOrderStatus.TRANSMITTED)

	def on_cancel(self):
		self.notify_reference_docs(status=PaymentOrderStatus.CANCELLED)

	def on_trash(self):
		self.notify_reference_docs(status=PaymentOrderStatus.CANCELLED)

	def notify_reference_docs(self, status: PaymentOrderStatus):
		for payment in self.payments:
			if payment.reference_doctype and payment.reference_name:
				doc = frappe.get_doc(payment.reference_doctype, payment.reference_name)
				doc.run_method("sepa_payment_order_status_changed", payment.reference_row_name, status)

	def to_sepa_credit_transfer(self) -> "SEPACreditTransfer":
		"""
		NOTE: call register_fintech() before calling this method.
		"""

		from fintech.sepa import Account, Amount, SEPACreditTransfer

		debtor_account = Account(
			iban=self.iban.replace(" ", ""),
			name=self.company,
		)
		transfer = SEPACreditTransfer(
			account=debtor_account,
			batch=self.batch_booking == "Process as batch",
		)
		for payment in self.payments:
			transfer.add_transaction(
				account=Account(
					iban=payment.iban.replace(" ", ""),
					name=payment.recipient,
				),
				amount=Amount(
					value=payment.amount,
					currency=payment.currency,
				),
				purpose=payment.purpose,
				eref=payment.eref,
				charges=payment.charges,
			)

		return transfer


@frappe.whitelist(methods=["POST"])
def download_xml_file(sepa_payment_order: str):
	payment_order: SEPAPaymentOrder = frappe.get_doc("SEPA Payment Order", sepa_payment_order)
	payment_order.check_permission("submit")

	register_fintech()

	transfer = payment_order.to_sepa_credit_transfer()
	xml = transfer.render()

	frappe.response["filename"] = f"{payment_order.name}.xml"
	frappe.response["filecontent"] = xml
	frappe.response["type"] = "binary"

	payment_order.transmission_datetime = now_datetime()
	payment_order.transmission_type = "DOWNLOADED"
	payment_order.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def send_to_bank(
	sepa_payment_order: str, ebics_user_id: str, sig_passphrase: str, passphrase: str | None = None
):
	payment_order: SEPAPaymentOrder = frappe.get_doc("SEPA Payment Order", sepa_payment_order)
	payment_order.check_permission("submit")

	ebics_user = frappe.get_doc("EBICS User", ebics_user_id)
	ebics_user.check_permission("read")

	ebics_manager = get_ebics_manager(
		ebics_user=ebics_user,
		passphrase=passphrase,
		sig_passphrase=sig_passphrase,
	)

	transfer = payment_order.to_sepa_credit_transfer()
	ebics_order_id = transfer.send(ebics_client=ebics_manager.get_client(), use_ful=True)

	payment_order.transmission_datetime = now_datetime()
	payment_order.ebics_order_id = ebics_order_id
	payment_order.transmission_type = "SENT_VIA_EBICS"
	payment_order.save(ignore_permissions=True)
