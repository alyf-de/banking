from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc

from banking.ebics.doctype.sepa_payment_order.sepa_payment_order import PaymentOrderStatus

if TYPE_CHECKING:
	from erpnext.accounts.doctype.bank.bank import Bank
	from erpnext.accounts.doctype.bank_account.bank_account import BankAccount
	from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice


@frappe.whitelist()
def make_sepa_payment_order(source_name: str, target_doc=None):
	def set_missing_values(source, target):
		if not target.bank_account:
			bank_account = frappe.db.get_value(
				"Bank Account",
				{"is_company_account": 1, "company": source.company, "disabled": 0},
				["name", "iban", "bank"],
				order_by="is_default DESC",
				as_dict=True,
			)
			if bank_account:
				target.bank_account = bank_account.get("name")
				target.iban = bank_account.get("iban")
				target.bank = bank_account.get("bank")

	def process_payment(source, target, source_parent):
		target.recipient = source_parent.supplier_name
		target.purpose = source_parent.bill_no
		target.currency = source_parent.currency
		target.eref = target.reference_name

		is_employee_advance_paid = (
			hasattr(source_parent, "business_trip") and source_parent.business_trip and
			hasattr(source_parent, "business_trip_employee") and source_parent.business_trip_employee and
			hasattr(source_parent, "advance_paid_by_employee") and source_parent.advance_paid_by_employee
		)

		if is_employee_advance_paid:
			# Get the Bank Account linked to the Employee
			bank_account = frappe.db.get_value(
				"Bank Account",
				{"party_type": "Employee", "party": source_parent.business_trip_employee, "disabled": 0},
				["iban", "bank"],
				order_by="is_default DESC",
				as_dict=True,
			)
			# If employee advance paid but no employee bank account found, leave empty
			# Do not fall back to supplier account as employee should receive the payment
		else:
			# Regular supplier logic
			if source_parent.supplier_bank_account:
				# Prefer the Supplier Bank Account set on the Purchase Invoice
				bank_account = frappe.db.get_value(
					"Bank Account",
					source_parent.supplier_bank_account,
					["iban", "bank"],
					as_dict=True,
				)

			if not bank_account:
				# Fallback to the (default) Bank Account linked to the Supplier
				bank_account = frappe.db.get_value(
					"Bank Account",
					{"party_type": "Supplier", "party": source_parent.supplier, "disabled": 0},
					["iban", "bank"],
					order_by="is_default DESC",
					as_dict=True,
				)

		if bank_account:
			if bank_account.get("bank"):
				target.swift_number = frappe.db.get_value("Bank", bank_account["bank"], "swift_number")
			target.iban = bank_account.get("iban")

	return get_mapped_doc(
		"Purchase Invoice",
		source_name,
		{
			"Purchase Invoice": {
				"doctype": "SEPA Payment Order",
				"validation": {"docstatus": ("=", 1), "status": ("!=", "Paid")},
			},
			"Payment Schedule": {
				"doctype": "SEPA Payment",
				"field_map": {
					"outstanding": "amount",
					"name": "reference_row_name",
					"parent": "reference_name",
					"parenttype": "reference_doctype",
				},
				"condition": lambda payment: round(payment.outstanding, 2) > 0,
				"postprocess": process_payment,
			},
		},
		target_doc,
		postprocess=set_missing_values,
	)


@frappe.whitelist()
def make_bulk_sepa_payment_order(source_names: str):
	target_doc = None
	for source_name in frappe.parse_json(source_names):
		if not isinstance(source_name, str):
			raise TypeError

		target_doc = make_sepa_payment_order(source_name, target_doc)

	return target_doc


def sepa_payment_order_status_changed(
	doc: "PurchaseInvoice", method: str, payment_schedule_row_name: str, status: PaymentOrderStatus
):
	"""Called via hooks when a linked SEPA Payment Order changes."""
	for scheduled_payment in doc.payment_schedule:
		if scheduled_payment.name == payment_schedule_row_name:
			scheduled_payment.sepa_payment_order_status = status.value
			break

	doc.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def create_supplier_bank_account(
	iban: str, supplier: str, supplier_name: str, bank: str | None = None
) -> str:
	_iban = iban.replace(" ", "").upper()

	existing_bank_account = frappe.db.exists("Bank Account", {"iban": _iban})
	if existing_bank_account:
		return existing_bank_account

	if not bank:
		if _iban.startswith("DE"):
			bank = create_bank(_iban)
		else:
			frappe.throw(_("For non-German IBANs, a Bank must be provided."))

	doc: BankAccount = frappe.new_doc("Bank Account")
	doc.iban = _iban
	doc.bank = bank
	doc.party_type = "Supplier"
	doc.party = supplier
	doc.account_name = supplier_name
	doc.save()

	return doc.name


def create_bank(iban: str) -> str:
	import kontocheck

	kontocheck.lut_load()

	bank_name = kontocheck.get_bankname(iban)
	swift_number = kontocheck.get_bic(iban)

	existing_bank = frappe.db.exists("Bank", {"swift_number": swift_number})
	if existing_bank:
		return existing_bank

	doc: Bank = frappe.new_doc("Bank")
	doc.bank_name = bank_name
	doc.swift_number = swift_number
	doc.insert()

	return doc.name
