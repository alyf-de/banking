# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt
from typing import TYPE_CHECKING

import frappe
import kontocheck
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import nowdate

from banking.ebics.utils import get_ebics_manager, register_fintech

if TYPE_CHECKING:
	from fintech.sepa import SEPACreditTransfer


class SEPAPaymentOrder(Document):
	def validate(self):
		kontocheck.lut_load()

		if not kontocheck.check_iban(self.iban):
			frappe.throw(_("IBAN {0} is invalid.").format(self.iban))

		for payment in self.payments:
			if not kontocheck.check_iban(payment.iban):
				frappe.throw(_("Row {0}: IBAN {1} is invalid.").format(payment.idx, payment.iban))

	def on_submit(self):
		pass

	def to_sepa_credit_transfer(self) -> "SEPACreditTransfer":
		"""
		NOTE: call register_fintech() before calling this method.
		"""

		from fintech.sepa import Account, Amount, SEPACreditTransfer

		debtor_account = Account(
			iban=self.iban,
			name=self.company,
		)
		transfer = SEPACreditTransfer(
			account=debtor_account,
			batch=self.batch_booking == "Process as batch",
		)
		for payment in self.payments:
			transfer.add_transaction(
				account=Account(
					iban=payment.iban,
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
def download_xml_file(sepa_payment_order: str):
	payment_order: SEPAPaymentOrder = frappe.get_doc("SEPA Payment Order", sepa_payment_order)
	payment_order.check_permission("read")

	register_fintech()

	transfer = payment_order.to_sepa_credit_transfer()
	xml = transfer.render()

	frappe.response["filename"] = f"{payment_order.name}.xml"
	frappe.response["filecontent"] = xml
	frappe.response["type"] = "binary"


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
	ebics_order_id = transfer.send(ebics_client=ebics_manager.get_client())

	payment_order.db_set({"transmission_date": nowdate(), "ebics_order_id": ebics_order_id})
