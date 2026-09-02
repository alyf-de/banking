import frappe


def execute():
	"""Copy the previously linked Company name into the new organization_name field."""
	if "company" not in frappe.db.get_table_columns("EBICS User"):
		return

	eu = frappe.qb.DocType("EBICS User")
	frappe.qb.update(eu).set(eu.organization_name, eu.company).where(eu.company.isnotnull()).run()
