from datetime import date
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt
from frappe.utils.data import getdate

from banking.ebics.doctype.sepa_payment_order.sepa_payment_order import PaymentOrderStatus

if TYPE_CHECKING:
	from hrms.hr.doctype.expense_claim.expense_claim import ExpenseClaim
	from hrms.hr.doctype.expense_claim_detail.expense_claim_detail import ExpenseClaimDetail

	from banking.ebics.doctype.sepa_payment.sepa_payment import SEPAPayment


@frappe.whitelist()
def make_sepa_payment_order(source_name: str, target_doc: str | Document | None = None):
	if frappe.db.get_value("Expense Claim", source_name, "sepa_payment_order_status"):
		frappe.throw(_("A SEPA Payment Order already exists for Expense Claim {0}.").format(source_name))

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

	def process_payment(source: "ExpenseClaimDetail", target: "SEPAPayment", source_parent: "ExpenseClaim"):
		claim = source_parent
		target.recipient = claim.employee_name
		target.purpose = _get_employee_purpose(claim)

		bank_account = _get_recipients_bank_account(claim)

		if bank_account and bank_account.get("iban"):
			target.iban = bank_account.get("iban")
			if bank_account.get("bank"):
				swift_number, bank_name = frappe.db.get_value(
					"Bank", bank_account["bank"], ["swift_number", "bank_name"]
				)
				target.swift_number = swift_number
				target.bank_name = bank_name
		else:
			employee_iban = frappe.db.get_value("Employee", claim.employee, "iban")
			if employee_iban:
				target.iban = employee_iban
			else:
				frappe.throw(_("No IBAN found for Employee {0}.").format(claim.employee))

		target.currency = frappe.db.get_value("Company", claim.company, "default_currency")
		target.eref = target.reference_name
		target.amount = get_sepa_payment_amount(
			claim,
			method="get_mapped_doc",
			reference_row_name=source.name,
			execution_date=getdate(),
		)

	return get_mapped_doc(
		"Expense Claim",
		source_name,
		{
			"Expense Claim": {
				"doctype": "SEPA Payment Order",
				"validation": {
					"docstatus": ("=", 1),
					"approval_status": ("=", "Approved"),
					"status": ("!=", "Paid"),
				},
			},
			"Expense Claim Detail": {
				"doctype": "SEPA Payment",
				"field_map": {
					"name": "reference_row_name",
					"parent": "reference_name",
					"parenttype": "reference_doctype",
				},
				"condition": lambda row: row.idx == 1
				and flt(row.parent_doc.grand_total) - flt(row.parent_doc.total_amount_reimbursed) > 0.0,
				"postprocess": process_payment,
			},
		},
		target_doc,
		postprocess=set_missing_values,
	)


def _get_employee_purpose(claim: "ExpenseClaim"):
	"""Return the bank transfer purpose for an expense claim reimbursement.

	Example: "EC-00001, 2025-03-01"
	"""
	reference = ", ".join(str(ref).strip() for ref in [claim.name, claim.posting_date] if ref)
	return reference.strip()


def _get_recipients_bank_account(claim: "ExpenseClaim"):
	return frappe.db.get_value(
		"Bank Account",
		{"party_type": "Employee", "party": claim.employee, "disabled": 0},
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
	doc: "ExpenseClaim", method: str, reference_row_name: str, status: PaymentOrderStatus
):
	"""Called via hooks when a linked SEPA Payment Order changes."""
	doc.sepa_payment_order_status = status.value
	doc.save(ignore_permissions=True)


def get_sepa_payment_amount(
	doc: "ExpenseClaim", method: str, reference_row_name: str, execution_date: date
) -> float:
	"""Return outstanding amount. No discount logic."""
	precision = doc.precision("grand_total")
	outstanding = flt(doc.grand_total, precision) - flt(doc.total_amount_reimbursed, precision)
	return max(0, outstanding)
