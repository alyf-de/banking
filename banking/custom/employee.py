import frappe
from frappe import _


def validate(doc, event):
	if hasattr(doc, "iban") and doc.has_value_changed("iban") and doc.iban:
		frappe.msgprint(
			_(
				"IBAN on Employee is not used in SEPA Payment Orders. Please use Bank Account instead for payment processing."
			),
			title=_("IBAN Warning: Not used in SEPA Payment Orders"),
			indicator="orange",
		)
