import frappe
from frappe import _


def validate(doc, event):
	if hasattr(doc, "iban") and doc.has_value_changed("iban") and doc.iban:
		if frappe.db.exists(
			"Bank Account",
			{"party_type": "Employee", "party": doc.name, "disabled": 0},
		):
			frappe.msgprint(
				_(
					"The IBAN in this form will not be used in SEPA Payment Orders because a Bank Account is already linked to this Employee."
				),
				title=_("IBAN Warning: Not used in SEPA Payment Orders"),
				indicator="orange",
			)
