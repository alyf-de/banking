import frappe
from frappe.core.utils import find
from frappe.utils import flt

from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_payment_entry,
	split_invoices_based_on_payment_terms,
)
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction


class CustomBankTransaction(BankTransaction):
	def add_payment_entries(self, vouchers):
		"Add the vouchers with zero allocation. Save() will perform the allocations and clearance"
		if self.unallocated_amount <= 0.0:
			frappe.throw(
				frappe._("Bank Transaction {0} is already fully reconciled").format(self.name)
			)

		pe_length_before = len(self.payment_entries)
		invoices_to_bill = []

		for voucher in vouchers:
			if find(
				self.payment_entries,
				lambda x: x.payment_document == voucher["payment_doctype"]
				and x.payment_entry == voucher["payment_name"],
			):
				continue  # Can't add same voucher twice

			payment_doctype, payment_name = voucher["payment_doctype"], voucher["payment_name"]
			outstanding_amount = self.get_outstanding_amount(payment_doctype, payment_name)

			if outstanding_amount > 0:
				# Make Payment Entry against the unpaid invoice, link PE to Bank Transaction
				invoices_to_bill.append((payment_doctype, payment_name, outstanding_amount))
			else:
				self.add_to_payment_entry(payment_doctype, payment_name)

		# Make single PE against multiple invoices
		if invoices_to_bill:
			payment_name = self.make_pe_against_invoices(invoices_to_bill)
			payment_doctype = "Payment Entry"  # Change doctype to PE
			self.add_to_payment_entry(payment_doctype, payment_name)

		# runs on_update_after_submit
		if len(self.payment_entries) != pe_length_before:
			self.save()

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

	def make_pe_against_invoice(self, payment_doctype, payment_name, outstanding_amount):
		bank_account = frappe.db.get_value("Bank Account", self.bank_account, "account")
		payment_entry = get_payment_entry(
			payment_doctype,
			payment_name,
			party_amount=min(self.unallocated_amount, outstanding_amount),
			bank_account=bank_account,
		)
		payment_entry.reference_no = self.reference_number or payment_name
		payment_entry.submit()
		return payment_entry.name

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
		)
		payment_entry = frappe.new_doc("Payment Entry")
		payment_entry.update(payment_entry_dict)
		payment_entry.party = (
			self.party
			or frappe.db.get_value(
				invoices_to_bill[0][0],
				invoices_to_bill[0][1],
				payment_entry_dict.party_type.lower(),
			),
		)

		if payment_entry_dict.payment_type == "Receive":
			payment_entry.paid_to = bank_account
		else:
			payment_entry.paid_from = bank_account

		invoices_to_split = []
		for invoice in invoices_to_bill:
			invoice_data = frappe.db.get_value(
				invoice[0],
				invoice[1],
				[
					"name as voucher_no",
					"posting_date",
					"base_grand_total as invoice_amount",
					"outstanding_amount",
					"due_date",
				],
				as_dict=True,
			)
			invoice_data["voucher_type"] = invoice[0]
			invoices_to_split.append(invoice_data)

		invoices = split_invoices_based_on_payment_terms(invoices_to_split, self.company)

		to_allocate = self.unallocated_amount
		for row in invoices:
			row_allocated_amount = min(row.outstanding_amount, to_allocate)
			row.allocated_amount = row_allocated_amount
			row.reference_doctype = row.voucher_type
			row.reference_name = row.voucher_no
			payment_entry.append("references", row)

			to_allocate -= row_allocated_amount
			if to_allocate <= 0:
				break

		payment_entry.submit()
		return payment_entry.name
