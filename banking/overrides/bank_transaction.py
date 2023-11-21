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
		# avoid mutating self.unallocated_amount (is set by erpnext on submit/update after submit)
		unallocated_amount = flt(self.unallocated_amount)

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
				outstanding_amount = get_outstanding_amount(payment_doctype, payment_name)
				allocated_by_voucher = min(unallocated_amount, outstanding_amount)

				if outstanding_amount > 0:
					# Make Payment Entry against the unpaid invoice, link PE to Bank Transaction
					payment_name = self.make_payment_entry(
						payment_doctype, payment_name, allocated_by_voucher
					)
					payment_doctype = "Payment Entry"  # Change doctype to PE

				pe = {
					"payment_document": payment_doctype,
					"payment_entry": payment_name,
					"allocated_amount": 0.0,  # Temporary
				}
				self.append("payment_entries", pe)
				added = True

				# Reduce unallocated amount
				unallocated_amount = flt(
					unallocated_amount - allocated_by_voucher, self.precision("unallocated_amount")
				)

		# runs on_update_after_submit
		if added:
			self.save()

	def make_payment_entry(
		self, payment_doctype: str, payment_name: str, to_allocate: float
	):
		bank_account = frappe.db.get_value("Bank Account", self.bank_account, "account")
		if payment_doctype == "Expense Claim":
			from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

			payment_entry = get_payment_entry_for_employee(
				payment_doctype,
				payment_name,
				party_amount=to_allocate,
				bank_account=bank_account,
			)
		else:
			payment_entry = get_payment_entry(
				payment_doctype,
				payment_name,
				party_amount=to_allocate,
				bank_account=bank_account,
			)

		payment_entry.reference_no = self.reference_number or payment_name
		payment_entry.reference_date = self.date
		payment_entry.submit()

		return payment_entry.name


def get_outstanding_amount(payment_doctype, payment_name):
	if payment_doctype not in ("Sales Invoice", "Purchase Invoice", "Expense Claim"):
		return 0

	if payment_doctype == "Expense Claim":
		ec = frappe.get_doc(payment_doctype, payment_name)
		return flt(
			ec.total_sanctioned_amount - ec.total_amount_reimbursed,
			ec.precision("total_sanctioned_amount"),
		)

	invoice = frappe.get_doc(payment_doctype, payment_name)
	return flt(invoice.outstanding_amount, invoice.precision("outstanding_amount"))
