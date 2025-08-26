import frappe
from pypika.functions import Replace


def execute():
	"""Remove spaces from IBAN in all bank accounts"""
	ba = frappe.qb.DocType("Bank Account")
	frappe.qb.update(ba).set(ba.iban, Replace(ba.iban, " ", "")).where(ba.iban.like("% %")).run()
