from typing import TYPE_CHECKING

import frappe
from frappe.model.mapper import get_mapped_doc

from banking.ebics.doctype.sepa_payment_order.sepa_payment_order import PaymentOrderStatus

if TYPE_CHECKING:
	from erpnext.accounts.doctype.payment_schedule.payment_schedule import PaymentSchedule
	from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice

	from banking.ebics.doctype.sepa_payment.sepa_payment import SEPAPayment


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

	def process_payment(source: "PaymentSchedule", target: "SEPAPayment", source_parent: "PurchaseInvoice"):
		pi = source_parent
		pay_to_employee = all(
			(
				hasattr(pi, "business_trip") and pi.business_trip,
				hasattr(pi, "business_trip_employee") and pi.business_trip_employee,
				hasattr(pi, "pay_to_employee") and pi.pay_to_employee,
			)
		)

		target.recipient = (
			frappe.db.get_value("Employee", pi.business_trip_employee, "employee_name")
			if pay_to_employee
			else pi.supplier_name
		)
		target.purpose = f"{pi.bill_no} ({pi.business_trip})" if pay_to_employee else pi.bill_no

		bank_account = _get_recipients_bank_account(pi, pay_to_employee)
		if bank_account:
			if bank_account.get("bank"):
				target.swift_number = frappe.db.get_value("Bank", bank_account["bank"], "swift_number")
			target.iban = bank_account.get("iban")

		target.currency = pi.currency
		target.eref = target.reference_name

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


def _get_recipients_bank_account(purchase_invoice: "PurchaseInvoice", pay_to_employee: bool):
	"""
	Get the recipient's bank account based on whether it's an employee advance payment or regular supplier payment.
	"""
	if pay_to_employee:
		# Prefer the Employee Bank Account set on the Purchase Invoice
		# Fallback to the (default) Bank Account linked to the Employee
		filters = purchase_invoice.employee_bank_account or {
			"party_type": "Employee",
			"party": purchase_invoice.business_trip_employee,
			"disabled": 0,
		}
	else:
		# Prefer the Supplier Bank Account set on the Purchase Invoice
		# Fallback to the (default) Bank Account linked to the Supplier
		filters = purchase_invoice.supplier_bank_account or {
			"party_type": "Supplier",
			"party": purchase_invoice.supplier,
			"disabled": 0,
		}

	return frappe.db.get_value(
		"Bank Account",
		filters,
		["iban", "bank"],
		order_by="is_default DESC",
		as_dict=True,
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
