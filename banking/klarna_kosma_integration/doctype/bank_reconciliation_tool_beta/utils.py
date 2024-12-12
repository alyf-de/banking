import frappe
from frappe import _

from pypika.queries import Table
from pypika.terms import Case, Field
from frappe.query_builder.functions import CustomFunction, Cast

Instr = CustomFunction("INSTR", ["a", "b"])
RegExpReplace = CustomFunction("REGEXP_REPLACE", ["a", "b", "c"])

# NOTE:
# Ranking min: 1 (nothing matches), max: 7 (everything matches)

# Types of matches:
# amount_match: if amount in voucher EQ amount in bank statement
# party_match: if party in voucher EQ party in bank statement
# date_match: if date in voucher EQ date in bank statement
# reference_number_match: if ref in voucher EQ ref in bank statement
# name_in_desc_match: if name in voucher IN bank statement description
# ref_in_desc_match: if ref in voucher IN bank statement description


def amount_rank_condition(amount: Field, bank_amount: float) -> Case:
	"""Get the rank query for amount matching."""
	return frappe.qb.terms.Case().when(amount == bank_amount, 1).else_(0)


def ref_equality_condition(reference_no: Field, bank_reference_no: str) -> Case:
	"""Get the rank query for reference number matching."""
	if not bank_reference_no or bank_reference_no == "NOTPROVIDED":
		# If bank reference number is not provided, then it is not a match
		return Cast(0, "int")

	return frappe.qb.terms.Case().when(reference_no == bank_reference_no, 1).else_(0)


def get_description_match_condition(
	description: str, table: Table, column_name: str = "name"
) -> Case:
	"""Get the description match condition for a column.

	Args:
	description: The bank transaction description to search in
	column_name: The document column to match against (e.g., expense_claim.name, purchase_invoice.bill_no)

	Returns:
	A query condition that will be 1 if the description contains the document number
	and 0 otherwise.
	"""
	if not description:
		return Cast(0, "int")

	column_name = column_name or "name"
	column = table[column_name]
	# Perform replace if the column is the name, else the column value is ambiguous
	# Eg. column_name = "custom_ref_no" and its value = "tuf5673i" should be untouched
	if column_name == "name":
		return (
			frappe.qb.terms.Case()
			.when(
				Instr(description, RegExpReplace(column, r"^[^0-9]*", "")) > 0,
				1,
			)
			.else_(0)
		)
	else:
		return (
			frappe.qb.terms.Case()
			.when(
				column.notnull() & (column != "") & (Instr(description, column) > 0),
				1,
			)
			.else_(0)
		)


def get_reference_field_map() -> dict:
	"""Get the reference field map for the document types from Banking Settings.
	Returns: {"sales_invoice": "custom_field_name", ...}
	"""

	def _validate_and_get_field(row: dict) -> str:
		is_docfield = frappe.db.exists(
			"DocField", {"fieldname": row.field_name, "parent": row.document_type}
		)
		is_custom = frappe.db.exists(
			"Custom Field", {"fieldname": row.field_name, "dt": row.document_type}
		)
		if not (is_docfield or is_custom):
			frappe.throw(
				title=_("Invalid Field"),
				msg=_(
					"Field {} does not exist in {}. Please check the configuration in Banking Settings."
				).format(frappe.bold(row.field_name), frappe.bold(row.document_type)),
			)

		return row.field_name

	reference_fields = frappe.get_all(
		"Banking Reference Mapping",
		filters={
			"parent": "Banking Settings",
		},
		fields=["document_type", "field_name"],
	)

	return {
		frappe.scrub(row.document_type): _validate_and_get_field(row)
		for row in reference_fields
	}
