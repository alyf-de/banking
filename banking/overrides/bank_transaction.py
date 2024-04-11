import frappe
from frappe.core.utils import find
from frappe.utils import flt

from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_payment_entry,
	split_invoices_based_on_payment_terms,
)
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction

DOCTYPE, DOCNAME, AMOUNT, PARTY = 0, 1, 2, 3


class CustomBankTransaction(BankTransaction):
	def add_payment_entries(self, vouchers):
		"Add the vouchers with zero allocation. Save() will perform the allocations and clearance"
		if self.unallocated_amount <= 0.0:
			frappe.throw(
				frappe._("Bank Transaction {0} is already fully reconciled").format(self.name)
			)

<<<<<<< HEAD
		added = False
		# avoid mutating self.unallocated_amount (is set by erpnext on submit/update after submit)
		unallocated_amount = flt(self.unallocated_amount)
=======
		pe_length_before = len(self.payment_entries)
		invoices_to_bill = []
>>>>>>> 5e03cab (feat: Create single PE to reconcile multiple unpaid invoices)

		for voucher in vouchers:
			voucher_type, voucher_name = voucher["payment_doctype"], voucher["payment_name"]
			if find(
				self.payment_entries,
				lambda x: x.payment_document == voucher_type and x.payment_entry == voucher_name,
			):
				continue  # Can't add same voucher twice

<<<<<<< HEAD
<<<<<<< HEAD
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
=======
			payment_doctype, payment_name = voucher["payment_doctype"], voucher["payment_name"]
			outstanding_amount = self.get_outstanding_amount(payment_doctype, payment_name)

			if outstanding_amount > 0:
				# Make Payment Entry against the unpaid invoice, link PE to Bank Transaction
				invoices_to_bill.append((payment_doctype, payment_name, outstanding_amount))
			else:
				self.add_to_payment_entry(payment_doctype, payment_name)
>>>>>>> 5e03cab (feat: Create single PE to reconcile multiple unpaid invoices)

		# Make single PE against multiple invoices
		if invoices_to_bill:
			payment_name = self.make_pe_against_invoices(invoices_to_bill)
			payment_doctype = "Payment Entry"  # Change doctype to PE
			self.add_to_payment_entry(payment_doctype, payment_name)
=======
			outstanding_amount = get_outstanding_amount(voucher_type, voucher_name)
			allocated_by_voucher = min(unallocated_amount, outstanding_amount)

			if (
				voucher_type
				in (
					"Sales Invoice",
					"Purchase Invoice",
					"Expense Claim",
				)
				and outstanding_amount > 0.0
			):
				# Make PE against the unpaid invoice, link PE to Bank Transaction
				invoices_to_bill.append(
					(voucher_type, voucher_name, allocated_by_voucher, voucher.get("party"))
				)
			else:
				self.add_to_payment_entry(voucher_type, voucher_name)
>>>>>>> 6e5f3be (fix: Create single PE for multiple unpaid invoices)

				# Reduce unallocated amount
				unallocated_amount = flt(
					unallocated_amount - allocated_by_voucher, self.precision("unallocated_amount")
				)

		# Make single PE against multiple invoices
		if invoices_to_bill:
			payment_name = self.make_pe_against_invoices(invoices_to_bill)
			self.add_to_payment_entry("Payment Entry", payment_name)  # Change doctype to PE

		if len(self.payment_entries) != pe_length_before:
			self.save()  # runs on_update_after_submit

<<<<<<< HEAD
	def make_payment_entry(
		self, payment_doctype: str, payment_name: str, to_allocate: float
	):
=======
	def add_to_payment_entry(self, payment_doctype, payment_name):
		"""Add the payment entry to the bank transaction"""
		pe = {
			"payment_document": payment_doctype,
			"payment_entry": payment_name,
			"allocated_amount": 0.0,  # Temporary
		}
		self.append("payment_entries", pe)

	def get_outstanding_amount(self, payment_doctype, payment_name):
		if payment_doctype not in ("Sales Invoice", "Purchase Invoice"):
			return 0

		# Check if the invoice is unpaid
		return flt(frappe.db.get_value(payment_doctype, payment_name, "outstanding_amount"))

<<<<<<< HEAD
	def make_pe_against_invoice(self, payment_doctype, payment_name, outstanding_amount):
>>>>>>> 5e03cab (feat: Create single PE to reconcile multiple unpaid invoices)
=======
	def make_pe_against_invoices(self, invoices_to_bill):
		"""Make Payment Entry against multiple invoices."""
		self.validate_invoices_to_bill(invoices_to_bill)

>>>>>>> 6e5f3be (fix: Create single PE for multiple unpaid invoices)
		bank_account = frappe.db.get_value("Bank Account", self.bank_account, "account")
		first_invoice = invoices_to_bill[0]
		if first_invoice[DOCTYPE] == "Expense Claim":
			from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

			payment_entry = get_payment_entry_for_employee(
				first_invoice[DOCTYPE],
				first_invoice[DOCNAME],
				party_amount=first_invoice[AMOUNT],
				bank_account=bank_account,
			)
		else:
			payment_entry = get_payment_entry(
				first_invoice[DOCTYPE],
				first_invoice[DOCNAME],
				party_amount=first_invoice[AMOUNT],
				bank_account=bank_account,
			)
		payment_entry.reference_no = self.reference_number or first_invoice[DOCNAME]

<<<<<<< HEAD
<<<<<<< HEAD
		payment_entry.reference_no = self.reference_number or payment_name
		payment_entry.reference_date = self.date
		payment_entry.submit()

		return payment_entry.name

<<<<<<< HEAD

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
=======
	def make_pe_against_invoices(self, invoices_to_bill):
		"""Make Payment Entry against multiple invoices."""
		bank_account = frappe.db.get_value("Bank Account", self.bank_account, "account")

		payment_entry_dict = frappe._dict(
			{
				"company": self.company,
				"payment_type": "Receive" if self.deposit > 0.0 else "Pay",
				"reference_no": self.reference_number or invoices_to_bill[0][1],
				"reference_date": self.date,
				"party_type": "Customer" if self.deposit > 0.0 else "Supplier",
				"paid_amount": self.unallocated_amount,
				"received_amount": self.unallocated_amount,
			}
=======
		invoices = split_invoices_based_on_payment_terms(
			self.prepare_invoices_to_split(invoices_to_bill[1:]), self.company
>>>>>>> 6e5f3be (fix: Create single PE for multiple unpaid invoices)
=======
		# clear references to allocate invoices correctly with splits
		payment_entry.references = []
		invoices = split_invoices_based_on_payment_terms(
			self.prepare_invoices_to_split(invoices_to_bill), self.company
>>>>>>> bd0628a (test: Reconcile BT with unpaid invoices)
		)

		to_allocate = self.unallocated_amount
		for row in invoices:
			row_allocated_amount = min(row.outstanding_amount, to_allocate)  # partial allocation
			row.allocated_amount = row_allocated_amount
			row.reference_doctype = row.voucher_type
			row.reference_name = row.voucher_no
			payment_entry.append("references", row)

			to_allocate -= row_allocated_amount
			if to_allocate <= 0:
				break

<<<<<<< HEAD
		payment_entry.submit()
		return payment_entry.name
>>>>>>> 5e03cab (feat: Create single PE to reconcile multiple unpaid invoices)
=======
		payment_entry.paid_amount = sum(
			row.allocated_amount for row in payment_entry.references
		)
		payment_entry.submit()  # TODO: submit it after testing
		return payment_entry.name

	def prepare_invoices_to_split(self, invoices):
		invoices_to_split = []
		for invoice in invoices:
			invoice_data = frappe.db.get_value(
				invoice[DOCTYPE],
				invoice[DOCNAME],
				[
					"name as voucher_no",
					"posting_date",
					"base_grand_total as invoice_amount",
					"due_date",
				],
				as_dict=True,
			)
			invoice_data["outstanding_amount"] = invoice[AMOUNT]
			invoice_data["voucher_type"] = invoice[DOCTYPE]
			invoices_to_split.append(invoice_data)

		return invoices_to_split

	def validate_invoices_to_bill(self, invoices_to_bill):
		unique_doctypes = {invoice[DOCTYPE] for invoice in invoices_to_bill}
		if len(unique_doctypes) > 1:
			frappe.throw(
				frappe._("Cannot make Reconciliation Payment Entry against multiple doctypes")
			)

		unique_parties = {invoice[PARTY] for invoice in invoices_to_bill}
		if len(unique_parties) > 1:
			frappe.throw(
				frappe._("Cannot make Reconciliation Payment Entry against multiple parties")
			)


def get_outstanding_amount(payment_doctype, payment_name) -> float:
	if payment_doctype not in ("Sales Invoice", "Purchase Invoice", "Expense Claim"):
		return 0.0

	if payment_doctype == "Expense Claim":
		ec = frappe.get_doc(payment_doctype, payment_name)
		return flt(
			ec.total_sanctioned_amount - ec.total_amount_reimbursed,
			ec.precision("total_sanctioned_amount"),
		)

	invoice = frappe.get_doc(payment_doctype, payment_name)
	return flt(invoice.outstanding_amount, invoice.precision("outstanding_amount"))
>>>>>>> 6e5f3be (fix: Create single PE for multiple unpaid invoices)
