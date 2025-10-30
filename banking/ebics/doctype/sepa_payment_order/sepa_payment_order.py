# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt
import contextlib
from enum import StrEnum
from typing import TYPE_CHECKING

import frappe
import kontocheck
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import fmt_money, getdate, now_datetime

from banking.ebics.utils import get_ebics_manager, register_fintech

if TYPE_CHECKING:
	from datetime import date

	from fintech.sepa import SEPACreditTransfer

	from banking.ebics.doctype.sepa_payment.sepa_payment import SEPAPayment


class PaymentOrderStatus(StrEnum):
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
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from banking.ebics.doctype.sepa_payment.sepa_payment import SEPAPayment

		amended_from: DF.Link | None
		bank: DF.Link | None
		bank_account: DF.Link
		batch_booking: DF.Literal["Process individually", "Process as batch"]
		company: DF.Link
		ebics_order_id: DF.Data | None
		execution_date: DF.Date | None
		iban: DF.Data
		payments: DF.Table[SEPAPayment]
		reference_number: DF.Data | None
		swift_number: DF.Data | None
		transmission_datetime: DF.Datetime | None
		transmission_type: DF.Literal["", "DOWNLOADED", "SENT_VIA_EBICS"]
	# end: auto-generated types

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

	@frappe.whitelist()
	def update_payment_amounts(self):
		for payment in self.payments:
			new_amount = get_changed_payment_amount(payment, self.execution_date)
			if new_amount is None:
				continue

			payment.amount = new_amount
			frappe.msgprint(
				_("Amount updated to {0} in row {1}.").format(
					fmt_money(new_amount, currency=payment.currency), payment.idx
				)
			)

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


@frappe.whitelist()
def have_amounts_changed(sepa_payment_order: str):
	"""Return True if the payment amounts have changed since the last save.

	Runs before submit.
	"""
	payment_order: SEPAPaymentOrder = frappe.get_doc("SEPA Payment Order", sepa_payment_order)
	payment_order.check_permission("write")

	return any(
		get_changed_payment_amount(payment, payment_order.execution_date) is not None
		for payment in payment_order.payments
	)


def get_changed_payment_amount(payment: "SEPAPayment", execution_date: "date | None" = None) -> float | None:
	"""Call the reference doc's `get_sepa_payment_amount` method to get the outstanding amount.

	If the amount has changed, return the new amount. Otherwise, return None.
	"""
	if not payment.reference_doctype or not payment.reference_name:
		return None

	doc = frappe.get_doc(payment.reference_doctype, payment.reference_name)
	new_amount = doc.run_method(
		"get_sepa_payment_amount",
		payment.reference_row_name,
		getdate(execution_date) if execution_date else getdate(),
	)

	if new_amount is None:
		return None

	precision = payment.precision("amount")
	if round(new_amount, precision) != round(payment.amount, precision):
		return new_amount

	return None


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
