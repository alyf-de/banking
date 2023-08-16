import frappe
from frappe.utils import flt

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction


class CustomBankTransaction(BankTransaction):
	def add_payment_entries(self, vouchers):
		"Add the vouchers with zero allocation. Save() will perform the allocations and clearance"
		if 0.0 >= self.unallocated_amount:
			frappe.throw(
				frappe._("Bank Transaction {0} is already fully reconciled").format(self.name)
			)

		added = False
		for voucher in vouchers:
			# Can't add same voucher twice
			found = False
			for pe in self.payment_entries:
				if (
					pe.payment_document == voucher["payment_doctype"]
					and pe.payment_entry == voucher["payment_name"]
				):
					found = True

			if not found:
				payment_doctype, payment_name = voucher["payment_doctype"], voucher["payment_name"]

				if self.is_unpaid_invoice(payment_doctype, payment_name):
					# Make Payment Entry against the unpaid invoice, link PE to Bank Transaction
					payment_name = self.make_pe_against_invoice(payment_doctype, payment_name)
					payment_doctype = "Payment Entry"  # Change doctype to PE

				pe = {
					"payment_document": payment_doctype,
					"payment_entry": payment_name,
					"allocated_amount": 0.0,  # Temporary
				}
				self.append("payment_entries", pe)
				added = True

		# runs on_update_after_submit
		if added:
			self.save()

	def is_unpaid_invoice(self, payment_doctype, payment_name):
		is_invoice = payment_doctype in ("Sales Invoice", "Purchase Invoice")
		if not is_invoice:
			return False

		# Check if the invoice is unpaid
		return (
			flt(frappe.db.get_value(payment_doctype, payment_name, "outstanding_amount")) > 0
		)

	def make_pe_against_invoice(self, payment_doctype, payment_name):
		bank_account = frappe.db.get_value("Bank Account", self.bank_account, "account")
		payment_entry = get_payment_entry(
			payment_doctype, payment_name, bank_account=bank_account
		)
		payment_entry.reference_no = self.reference_number or payment_name
		payment_entry.submit()
		return payment_entry.name
