import frappe
from frappe import _
from frappe.core.utils import find
from frappe.utils import flt, getdate

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

		pe_length_before = len(self.payment_entries)
		unpaid_docs = ["Sales Invoice", "Purchase Invoice", "Expense Claim"]

		# Vouchers can either all be paid or all be unpaid
		if any(voucher["payment_doctype"] in unpaid_docs for voucher in vouchers):
			self.reconcile_invoices(vouchers)
		else:
			self.reconcile_paid_vouchers(vouchers)

		if len(self.payment_entries) != pe_length_before:
			self.save()  # runs on_update_after_submit

	def validate_period_closing(self):
		"""
		Check if the Bank Transaction date is after the latest period closing date.
		We cannot make PEs against this transaction's date (before period closing date).
		"""
		latest_period_close_date = frappe.db.get_value(
			"Period Closing Voucher",
			{"company": self.company, "docstatus": 1},
			"posting_date",
			order_by="posting_date desc",
		)
		if latest_period_close_date and getdate(self.date) <= getdate(
			latest_period_close_date
		):
			frappe.throw(
				_(
					"Due to Period Closing, you cannot reconcile unpaid vouchers with a Bank Transaction before {0}"
				).format(frappe.format(latest_period_close_date, "Date"))
			)

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

	def reconcile_paid_vouchers(self, vouchers):
		"""Reconcile paid vouchers with the Bank Transaction."""
		for voucher in vouchers:
			voucher_type, voucher_name = voucher["payment_doctype"], voucher["payment_name"]
			if self.is_duplicate_reference(voucher_type, voucher_name):
				continue

			self.add_to_payment_entry(voucher["payment_doctype"], voucher["payment_name"])

	def reconcile_invoices(self, vouchers):
		"""Reconcile unpaid invoices with the Bank Transaction."""
		invoices_to_bill = []
		for voucher in vouchers:
			voucher_type, voucher_name = voucher["payment_doctype"], voucher["payment_name"]
			if self.is_duplicate_reference(voucher_type, voucher_name):
				continue

			outstanding_amount = get_outstanding_amount(voucher_type, voucher_name)
			if (
				voucher_type
				not in (
					"Sales Invoice",
					"Purchase Invoice",
					"Expense Claim",
				)
				and outstanding_amount == 0.0
			):
				frappe.throw(_("Invalid Voucher Type"))

			# Make PE against the unpaid invoice, link PE to Bank Transaction
			invoices_to_bill.append(
				(voucher_type, voucher_name, outstanding_amount, voucher.get("party"))
			)

		# Make single PE against multiple invoices
		if invoices_to_bill:
			self.validate_period_closing()
			payment_name = self.make_pe_against_invoices(invoices_to_bill)
			self.add_to_payment_entry("Payment Entry", payment_name)  # Change doctype to PE

	def make_pe_against_invoices(self, invoices_to_bill):
		"""Make Payment Entry against multiple invoices."""
		self.validate_invoices_to_bill(invoices_to_bill)

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
				# make sure return invoice does not cause wrong payment type
				# return SI against a deposit should be considered as "Receive" (discount)
				# return SI against a withdrawal should be considered as "Pay" (refund)
				payment_type="Receive" if self.deposit > 0 else "Pay",
			)
		payment_entry.posting_date = self.date
		payment_entry.reference_no = self.reference_number or first_invoice[DOCNAME]
		payment_entry.reference_date = self.date

		# clear references to allocate invoices correctly with splits
		payment_entry.references = []
		invoices = split_invoices_based_on_payment_terms(
			self.prepare_invoices_to_split(invoices_to_bill), self.company
		)

		# First class pass for positive amounts, negative amounts adjust accordingly
		sum_postive, sum_negative = self.get_positive_and_negative_sums(invoices)
		for row in invoices:
			row.reference_doctype = row.voucher_type
			row.reference_name = row.voucher_no

			if row.outstanding_amount > 0:
				if sum_postive <= 0:
					continue
				row_allocated_amount = min(row.outstanding_amount, sum_postive)
				sum_postive -= row_allocated_amount
			else:
				if sum_negative <= 0:
					continue
				can_allocate = min(abs(row.outstanding_amount), sum_negative)
				row_allocated_amount = -1 * can_allocate
				sum_negative -= can_allocate

			row.allocated_amount = row_allocated_amount
			payment_entry.append("references", row)

		payment_entry.paid_amount = abs(
			sum(row.allocated_amount for row in payment_entry.references)
		)  # should not be negative
		payment_entry.submit()
		return payment_entry.name

	def prepare_invoices_to_split(self, invoices):
		invoices_to_split = []
		for invoice in invoices:
			is_expense_claim = invoice[DOCTYPE] == "Expense Claim"
			total_field = "grand_total" if is_expense_claim else "base_grand_total"
			due_date_field = "posting_date" if is_expense_claim else "due_date"

			invoice_data = frappe.db.get_value(
				invoice[DOCTYPE],
				invoice[DOCNAME],
				[
					"name as voucher_no",
					"posting_date",
					f"{total_field} as invoice_amount",
					f"{due_date_field} as due_date",
				],
				as_dict=True,
			)
			invoice_data["outstanding_amount"] = invoice[AMOUNT]
			invoice_data["voucher_type"] = invoice[DOCTYPE]
			invoices_to_split.append(invoice_data)

		return invoices_to_split

	def get_positive_and_negative_sums(self, invoices):
		"""
		Calculate a permissible positive and negative upper limit sum for the allocation.
		This will ensure that the allocated positive and negative amounts add up to the unallocated amount.
		"""
		sum_positive = (
			sum(
				invoice.outstanding_amount for invoice in invoices if invoice.outstanding_amount > 0
			)
			or 0.0
		)
		sum_negative = (
			abs(
				sum(
					invoice.outstanding_amount
					for invoice in invoices
					if invoice.outstanding_amount < 0
				)
			)
			or 0.0
		)
		if sum_negative > sum_positive:
			frappe.throw(
				title=_("Overallocated Returns"),
				msg=_(
					"The allocated amount cannot be negative. Please adjust the selected return vouchers."
				),
			)

		allocation = self.unallocated_amount - (sum_positive - sum_negative)
		if allocation < 0:
			sum_positive += allocation

		return sum_positive, sum_negative

	def validate_invoices_to_bill(self, invoices_to_bill):
		"""Validate if the invoices are of the same doctype and party."""
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

	def is_duplicate_reference(self, voucher_type, voucher_name):
		"""Check if the reference is already added to the Bank Transaction."""
		return find(
			self.payment_entries,
			lambda x: x.payment_document == voucher_type and x.payment_entry == voucher_name,
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


def on_update_after_submit(doc, event):
	"""Validate if the Bank Transaction is over-allocated."""
	to_allocate = flt(doc.withdrawal or doc.deposit)
	for entry in doc.payment_entries:
		to_allocate -= flt(entry.allocated_amount)
		if round(to_allocate, 2) < 0.0:
			symbol = frappe.db.get_value("Currency", doc.currency, "symbol")
			frappe.throw(
				msg=_("The Bank Transaction is over-allocated by {0} at row {1}.").format(
					frappe.bold(f"{symbol} {str(abs(to_allocate))}"), frappe.bold(entry.idx)
				),
				title=_("Over Allocation"),
			)
