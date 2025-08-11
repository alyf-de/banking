import frappe
from frappe.model.mapper import get_mapped_doc


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

		if source_parent.supplier_bank_account:
			# Prefer the Supplier Bank Account set on the Purchase Invoice
			bank_account = frappe.db.get_value(
				"Bank Account",
				source_parent.supplier_bank_account,
				["iban", "bank"],
				as_dict=True,
			)
		else:
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
