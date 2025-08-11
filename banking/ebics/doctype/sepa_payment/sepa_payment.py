# Copyright (c) 2025, ALYF GmbH and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SEPAPayment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		bank_name: DF.Data | None
		charges: DF.Literal["SHAR", "DEBT", "CRED"]
		currency: DF.Link
		eref: DF.Data | None
		iban: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		purpose: DF.Data
		recipient: DF.Data
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		reference_row_name: DF.Data | None
		swift_number: DF.Data | None
	# end: auto-generated types
	pass
