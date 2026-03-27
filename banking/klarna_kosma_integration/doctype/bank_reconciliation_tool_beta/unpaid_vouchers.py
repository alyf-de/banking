"""Create Journal Entries and Payment Entries against unpaid vouchers."""

from collections.abc import Callable
from typing import TYPE_CHECKING

import frappe
from erpnext import get_default_cost_center
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_payment_entry,
	split_invoices_based_on_payment_terms,
)
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

if TYPE_CHECKING:
	from banking.overrides.bank_transaction import CustomBankTransaction

DOCTYPE, DOCNAME, AMOUNT, PARTY = 0, 1, 2, 3


def get_payment_entries(
	bt: "CustomBankTransaction",
	vouchers: list,
	reconcile_multi_party: bool = False,
	extra_params: dict | None = None,
	*args,
	**kwargs,
):
	"""Reconcile unpaid invoices with the Bank Transaction."""
	if any(
		voucher["payment_doctype"] not in ("Sales Invoice", "Purchase Invoice", "Expense Claim")
		for voucher in vouchers
	):
		return

	invoices_to_bill = []
	for voucher in vouchers:
		voucher_type, voucher_name = voucher["payment_doctype"], voucher["payment_name"]
		if bt.is_duplicate_reference(voucher_type, voucher_name):
			continue

		outstanding_amount = get_outstanding_amount(voucher_type, voucher_name)
		# Make PE against the unpaid invoice, link PE to Bank Transaction
		invoices_to_bill.append((voucher_type, voucher_name, outstanding_amount, voucher.get("party")))

	# Make single PE against multiple invoices
	payments = []
	if invoices_to_bill:
		bt.validate_period_closing()
		if reconcile_multi_party:
			journal_entry = make_jv_against_invoices(bt, invoices_to_bill)
			# payment_doctype, payment_name, amount
			payments.append(
				{
					"payment_doctype": "Journal Entry",
					"payment_name": journal_entry.name,
					"amount": journal_entry.total_debit,
				}
			)
		else:
			payment_entry = make_pe_against_invoices(bt, invoices_to_bill)
			payments.append(
				{
					"payment_doctype": "Payment Entry",
					"payment_name": payment_entry.name,
					"amount": payment_entry.paid_amount,
				}
			)

	return payments


def make_jv_against_invoices(bt: "CustomBankTransaction", invoices_to_bill: list):
	"""Make Journal Entry against multiple invoices."""

	def _attach_invoice(row: dict, journal_entry: "Document") -> None:
		second_account = get_debtor_creditor_account(row)
		second_account_currency = frappe.db.get_value("Account", second_account, "account_currency")
		if second_account_currency != company_currency:
			frappe.throw(
				_(
					"The currency of the second account ({0}) must be the same as of the bank account ({1})"
				).format(second_account, company_currency)
			)
		journal_entry.append(
			"accounts",
			{
				"account": second_account,
				"credit_in_account_currency": row.allocated_amount if bt.deposit > 0 else 0.0,
				"debit_in_account_currency": row.allocated_amount if bt.withdrawal > 0 else 0.0,
				"party_type": row.get("party_type"),
				"party": row.get("party"),
				"cost_center": get_default_cost_center(company),
				"reference_type": row.voucher_type,
				"reference_name": row.voucher_no,
			},
		)

	validate_invoices_to_bill(invoices_to_bill, allow_multi_party=True)

	company_account = frappe.get_value("Bank Account", bt.bank_account, "account")
	company, company_currency = frappe.get_value("Account", company_account, ["company", "account_currency"])

	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Bank Entry"
	journal_entry.company = company
	journal_entry.posting_date = bt.date
	journal_entry.cheque_date = bt.date
	journal_entry.cheque_no = bt.reference_number
	journal_entry.title = bt.name
	journal_entry.user_remark = bt.description

	invoices = split_invoices_based_on_payment_terms(prepare_invoices_to_split(invoices_to_bill), bt.company)
	adjust_and_allocate_invoices(bt, invoices, journal_entry, action=_attach_invoice)

	total_allocated_amount = sum(row.allocated_amount for row in invoices)
	journal_entry.append(
		"accounts",
		{
			"account": company_account,
			"bank_account": bt.bank_account,
			"credit_in_account_currency": (total_allocated_amount if bt.withdrawal > 0 else 0.0),
			"debit_in_account_currency": total_allocated_amount if bt.deposit > 0 else 0.0,
			"cost_center": get_default_cost_center(company),
		},
	)

	journal_entry.submit()
	return journal_entry


def make_pe_against_invoices(bt: "CustomBankTransaction", invoices_to_bill: list):
	"""Make Payment Entry against multiple invoices."""

	def _attach_invoice(row: dict, payment_entry: "Document") -> None:
		row.reference_doctype = row.voucher_type
		row.reference_name = row.voucher_no
		payment_entry.append("references", row)

	validate_invoices_to_bill(invoices_to_bill)

	bank_account = frappe.db.get_value("Bank Account", bt.bank_account, "account")
	first_invoice = invoices_to_bill[0]

	# Detect multi-currency: the bank account currency differs from the
	# party (payable/receivable) account currency.  A USD invoice with a EUR
	# payable paid from a EUR bank is same-currency from the PE's perspective.
	is_multi_currency = False
	if first_invoice[DOCTYPE] != "Expense Claim":
		invoice_details = frappe.db.get_value(
			first_invoice[DOCTYPE],
			first_invoice[DOCNAME],
			["party_account_currency", "currency", "conversion_rate"],
			as_dict=True,
		)
		bank_account_currency = frappe.db.get_value("Account", bank_account, "account_currency")
		is_multi_currency = invoice_details.party_account_currency != bank_account_currency

	if is_multi_currency and len(invoices_to_bill) > 1:
		frappe.throw(
			_(
				"Reconciling multiple multi-currency invoices at once is not supported. Please reconcile one invoice at a time."
			)
		)

	if first_invoice[DOCTYPE] == "Expense Claim":
		from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

		payment_entry = get_payment_entry_for_employee(
			first_invoice[DOCTYPE],
			first_invoice[DOCNAME],
			party_amount=first_invoice[AMOUNT],
			bank_account=bank_account,
		)
	elif is_multi_currency:
		payment_entry = _create_multi_currency_pe(bt, first_invoice, invoice_details, bank_account)
	else:
		payment_entry = get_payment_entry(
			first_invoice[DOCTYPE],
			first_invoice[DOCNAME],
			party_amount=first_invoice[AMOUNT],
			bank_account=bank_account,
			# make sure return invoice does not cause wrong payment type
			# return SI against a deposit should be considered as "Receive" (discount)
			# return SI against a withdrawal should be considered as "Pay" (refund)
			payment_type="Receive" if bt.deposit > 0 else "Pay",
			reference_date=bt.date,
		)

	payment_entry.posting_date = bt.date
	payment_entry.reference_no = bt.reference_number or first_invoice[DOCNAME]
	payment_entry.reference_date = bt.date

	if is_multi_currency:
		# Refresh exchange rate for the bank transaction date (not the invoice date)
		# and recalculate amounts (exchange gain/loss deductions, etc.)
		payment_entry.source_exchange_rate = 0
		payment_entry.target_exchange_rate = 0
		payment_entry.set_exchange_rate()
		payment_entry.set_amounts()
	else:
		# clear references to allocate invoices correctly with splits
		payment_entry.references = []
		invoices = split_invoices_based_on_payment_terms(
			prepare_invoices_to_split(invoices_to_bill), bt.company
		)
		adjust_and_allocate_invoices(bt, invoices, payment_entry, action=_attach_invoice)

		payment_entry.paid_amount = abs(
			sum(row.allocated_amount for row in payment_entry.references)
		)  # should not be negative

	payment_entry.submit()
	return payment_entry


def _create_multi_currency_pe(
	bt: "CustomBankTransaction",
	invoice: tuple,
	invoice_details: frappe._dict,
	bank_account: str,
) -> "Document":
	"""Create a Payment Entry for a multi-currency invoice.

	When the party account currency (e.g. EUR) differs from the invoice/bank
	currency (e.g. USD), we pass bank_amount (from the Bank Transaction) to
	get_payment_entry. This bypasses the get_exchange_rate lookup inside
	get_payment_entry (which may return a different rate than the invoice's
	original conversion_rate) and ensures paid_amount is set correctly in the
	bank currency.
	"""
	bank_amount = bt.unallocated_amount
	party_amount = invoice[AMOUNT]  # outstanding in party_account_currency

	# For partial payments: cap party_amount to what the bank amount covers,
	# converted to party_account_currency using the invoice's conversion_rate.
	# Round to currency precision to avoid false partial payments from floating
	# point drift (e.g. stored outstanding 1140.07 vs computed 1140.0654...).
	currency_precision = cint(frappe.db.get_default("currency_precision")) or 2
	max_party_amount = flt(bank_amount * invoice_details.conversion_rate, currency_precision)
	party_amount = min(party_amount, max_party_amount)

	return get_payment_entry(
		invoice[DOCTYPE],
		invoice[DOCNAME],
		party_amount=party_amount,
		bank_account=bank_account,
		bank_amount=bank_amount,
		payment_type="Receive" if bt.deposit > 0 else "Pay",
	)


def prepare_invoices_to_split(invoices):
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
		invoice_data["party"] = invoice[PARTY]
		invoice_data["party_type"] = (
			"Customer"
			if invoice[DOCTYPE] == "Sales Invoice"
			else "Supplier"
			if invoice[DOCTYPE] == "Purchase Invoice"
			else "Employee"
		)
		invoices_to_split.append(invoice_data)

	return invoices_to_split


def get_positive_and_negative_sums(bt_deposit: float, bt_unallocated: float, invoices: list):
	"""
	Calculate a permissible positive and negative upper limit sum for the allocation.
	This will ensure that the allocated positive and negative amounts add up to the unallocated amount.
	"""
	sum_positive = (
		sum(invoice.outstanding_amount for invoice in invoices if invoice.outstanding_amount > 0) or 0.0
	)
	sum_negative = (
		abs(sum(invoice.outstanding_amount for invoice in invoices if invoice.outstanding_amount < 0)) or 0.0
	)
	validate_sums(bt_deposit, sum_positive, sum_negative, invoices)

	# Adjust the positive sum (trim it) if overallocated
	allocation = bt_unallocated - (sum_positive - sum_negative)
	if allocation < 0:
		sum_positive += allocation

	return sum_positive, sum_negative


def adjust_and_allocate_invoices(
	bt: "CustomBankTransaction",
	invoices: list,
	payment_voucher: "Document",
	action: Callable[[dict, Document], None],
) -> None:
	"""
	Adjust and allocate the invoicees to the payment voucher based on
	the unallocated amount.
	The `payment_voucher` object is mutated by param:action.
	"""
	sum_postive, sum_negative = get_positive_and_negative_sums(bt.deposit, bt.unallocated_amount, invoices)
	for row in invoices:
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
		# Attach the invoice to/Mutate the payment voucher
		action(row, payment_voucher)


def validate_sums(bt_deposit: float, sum_positive, sum_negative, invoices):
	"""Validate if the sum of positive and negative amounts is equal to the unallocated amount."""
	if sum_positive and not sum_negative:
		return

	if sum_negative and not sum_positive:
		# Only -ve invoices are allowed for opposite transactions
		# Eg. A return SINV can be matched with a withdrawal (it is a refund)
		invoice_doctype = "Sales Invoice" if bt_deposit > 0 else "Purchase Invoice"
		if invoices[0]["voucher_type"] != invoice_doctype:
			return

	if sum_negative > sum_positive:
		frappe.throw(
			title=_("Overallocated Returns"),
			msg=_("The allocated amount cannot be negative. Please adjust the selected return vouchers."),
		)


def validate_invoices_to_bill(invoices_to_bill: list, allow_multi_party: bool = False):
	"""Validate if the invoices are of the same doctype and party."""
	unique_doctypes = {invoice[DOCTYPE] for invoice in invoices_to_bill}
	if len(unique_doctypes) > 1:
		frappe.throw(frappe._("Cannot make Reconciliation Payment Entry against multiple doctypes"))

	if allow_multi_party:
		return

	unique_parties = {invoice[PARTY] for invoice in invoices_to_bill}
	if len(unique_parties) > 1:
		frappe.throw(frappe._("Cannot make Reconciliation Payment Entry against multiple parties"))


def get_debtor_creditor_account(invoice: dict) -> str | None:
	"""Get the debtor or creditor (intermediate) account based on the invoice type."""
	if invoice.get("voucher_type") == "Sales Invoice":
		account_field = "debit_to"
	elif invoice.get("voucher_type") == "Purchase Invoice":
		account_field = "credit_to"
	else:
		account_field = "payable_account"
	return frappe.db.get_value(invoice.get("voucher_type"), invoice.get("voucher_no"), account_field)


def get_outstanding_amount(payment_doctype, payment_name) -> float:
	if payment_doctype == "Expense Claim":
		ec = frappe.get_doc(payment_doctype, payment_name)
		return flt(
			ec.total_sanctioned_amount - ec.total_amount_reimbursed,
			ec.precision("total_sanctioned_amount"),
		)

	invoice = frappe.get_doc(payment_doctype, payment_name)
	return flt(invoice.outstanding_amount, invoice.precision("outstanding_amount"))
