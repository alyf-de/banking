"""Create Journal Entries and Payment Entries against unpaid vouchers."""

from collections.abc import Callable
from typing import TYPE_CHECKING

import frappe
from erpnext import get_company_currency, get_default_cost_center
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_payment_entry,
	split_invoices_based_on_payment_terms,
)
from erpnext.setup.utils import get_exchange_rate
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

if TYPE_CHECKING:
	from banking.overrides.bank_transaction import CustomBankTransaction

DOCTYPE, DOCNAME, AMOUNT, PARTY = 0, 1, 2, 3
SUPPORTED_RECONCILIATION_DOCTYPES = ("Sales Invoice", "Purchase Invoice", "Expense Claim")


def get_payment_entries(
	bt: "CustomBankTransaction",
	vouchers: list,
	reconcile_multi_party: bool = False,
	extra_params: dict | None = None,
	*args,
	**kwargs,
):
	"""Reconcile unpaid invoices with the Bank Transaction."""
	if any(voucher["payment_doctype"] not in SUPPORTED_RECONCILIATION_DOCTYPES for voucher in vouchers):
		return

	manual_reconcile_amounts = get_manual_reconcile_amounts(extra_params)
	if manual_reconcile_amounts and reconcile_multi_party:
		frappe.throw(_("Manual currency conversion is only available for single-voucher reconciliation."))

	if manual_reconcile_amounts and len(vouchers) != 1:
		frappe.throw(_("Manual currency conversion is only supported for a single voucher at a time."))

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
			payment_entry, bank_allocation_amount = make_pe_against_invoices(
				bt,
				invoices_to_bill,
				manual_reconcile_amounts=manual_reconcile_amounts,
			)
			payments.append(
				{
					"payment_doctype": "Payment Entry",
					"payment_name": payment_entry.name,
					"amount": bank_allocation_amount
					if bank_allocation_amount is not None
					else payment_entry.paid_amount,
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


def make_pe_against_invoices(
	bt: "CustomBankTransaction",
	invoices_to_bill: list,
	manual_reconcile_amounts: dict | None = None,
) -> tuple["Document", float | None]:
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

	manual_bank_amount = None
	if manual_reconcile_amounts:
		validate_manual_reconcile_currencies(bt, first_invoice, manual_reconcile_amounts)
		manual_bank_amount, manual_party_amount = get_capped_manual_reconcile_amounts(
			bt, first_invoice, manual_reconcile_amounts
		)

	if first_invoice[DOCTYPE] == "Expense Claim" and manual_reconcile_amounts:
		from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

		payment_entry = get_payment_entry_for_employee(
			first_invoice[DOCTYPE],
			first_invoice[DOCNAME],
			party_amount=manual_party_amount,
			bank_amount=manual_bank_amount,
			bank_account=bank_account,
		)
	elif first_invoice[DOCTYPE] == "Expense Claim":
		from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

		payment_entry = get_payment_entry_for_employee(
			first_invoice[DOCTYPE],
			first_invoice[DOCNAME],
			party_amount=first_invoice[AMOUNT],
			bank_account=bank_account,
		)
	elif manual_reconcile_amounts:
		payment_entry = get_payment_entry(
			first_invoice[DOCTYPE],
			first_invoice[DOCNAME],
			party_amount=manual_party_amount,
			bank_account=bank_account,
			bank_amount=manual_bank_amount,
			payment_type="Receive" if bt.deposit > 0 else "Pay",
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

	if manual_reconcile_amounts:
		# Keep party/bank amounts as initialized by get_payment_entry(party_amount, bank_amount).
		# Manual target_amount may intentionally differ from source_amount * exchange_rate,
		# and PE uses that delta to book exchange gain/loss while keeping difference_amount at zero.
		apply_manual_exchange_rate_to_payment_entry(payment_entry, bt, manual_reconcile_amounts)
	elif is_multi_currency:
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
	return payment_entry, manual_bank_amount


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
		reference_date=bt.date,
	)


def get_manual_reconcile_amounts(extra_params: dict | None) -> dict | None:
	"""Read optional manual FX inputs provided by the reconciliation UI.

	Business context: some bank statements are reconciled using a negotiated or
	statement rate instead of ERPNext's default rate lookup. This helper
	normalizes that optional payload early so posting logic can either follow the
	manual path or stay on the standard automatic conversion path. This payload is
	only meaningful for the single-voucher manual-conversion branch enforced in
	`get_payment_entries`.
	"""
	if not extra_params:
		return None

	manual_reconcile_amounts = extra_params.get("manual_reconcile_amounts")
	if not manual_reconcile_amounts:
		return None
	if not isinstance(manual_reconcile_amounts, dict):
		frappe.throw(_("Invalid manual reconcile amounts payload."))

	return manual_reconcile_amounts


def get_capped_manual_reconcile_amounts(
	bt: "CustomBankTransaction",
	first_invoice: tuple,
	manual_reconcile_amounts: dict,
) -> tuple[float, float]:
	"""Cap manual amounts to the real amounts that are still reconcilable.

	Business context: user-entered conversion figures must never allocate more
	than what remains on the bank transaction or voucher. Capping here keeps
	manual FX reconciliation safe for partial settlements and prevents
	over-allocation from creating inconsistent accounting outcomes.
	"""
	source_amount = flt(manual_reconcile_amounts.get("source_amount"), 9)
	target_amount = flt(manual_reconcile_amounts.get("target_amount"), 9)
	exchange_rate = flt(manual_reconcile_amounts.get("exchange_rate"), 9)

	if source_amount <= 0 or target_amount <= 0 or exchange_rate <= 0:
		frappe.throw(_("Manual reconcile amounts must be greater than zero."))

	bt_precision = bt.precision("unallocated_amount")
	if flt(source_amount, bt_precision) > flt(bt.unallocated_amount, bt_precision):
		frappe.throw(
			_(
				"The bank transaction has been modified since the dialog was loaded. Please refresh and try again."
			)
		)

	if source_amount <= 0:
		frappe.throw(_("Nothing to reconcile: source amount is fully capped by the bank transaction."))

	currency_precision = cint(frappe.db.get_default("currency_precision")) or 2
	voucher_outstanding_amount = abs(flt(first_invoice[AMOUNT], currency_precision))
	target_amount = min(flt(target_amount, currency_precision), voucher_outstanding_amount)
	if target_amount <= 0:
		frappe.throw(_("Target amount is not valid for the selected voucher."))

	if flt(first_invoice[AMOUNT]) < 0:
		target_amount *= -1

	return source_amount, target_amount


def validate_manual_reconcile_currencies(
	bt: "CustomBankTransaction",
	first_invoice: tuple,
	manual_reconcile_amounts: dict,
) -> None:
	"""Enforce that manual FX is applied to the expected currency pair only.

	Business context: reconciliation is anchored to one bank currency and one
	voucher settlement currency. These checks protect against stale client
	payloads or accidental currency mismatches that could post values to the
	wrong ledgers.
	"""
	source_currency = manual_reconcile_amounts.get("source_currency")
	target_currency = manual_reconcile_amounts.get("target_currency")

	if source_currency and source_currency != bt.currency:
		frappe.throw(_("Invalid source currency for manual reconciliation."))

	if not target_currency:
		return

	expected_target_currency = get_expected_target_currency(first_invoice)
	if expected_target_currency and target_currency != expected_target_currency:
		frappe.throw(_("Invalid target currency for manual reconciliation."))


def get_expected_target_currency(first_invoice: tuple) -> str | None:
	"""Resolve the ledger currency that the selected voucher should settle in.

	Business context: different voucher types settle in different accounting
	currencies (party account currency for invoices, company currency for expense
	claims). Returning a single expected target keeps manual FX validation and
	posting consistent across document types.
	"""
	voucher_doctype, voucher_name = first_invoice[DOCTYPE], first_invoice[DOCNAME]
	if voucher_doctype in {"Sales Invoice", "Purchase Invoice"}:
		return frappe.db.get_value(voucher_doctype, voucher_name, "party_account_currency")

	if voucher_doctype == "Expense Claim":
		company = frappe.db.get_value(voucher_doctype, voucher_name, "company")
		return get_company_currency(company)

	return None


def apply_manual_exchange_rate_to_payment_entry(
	payment_entry: "Document",
	bt: "CustomBankTransaction",
	manual_reconcile_amounts: dict,
) -> None:
	"""Apply user-approved FX rates so PE reflects statement-time economics.

	Business context: treasury may reconcile at a specific cross rate that differs
	from the system's day rate. By setting PE exchange rates from that manual
	input, posting can recognize the resulting exchange gain/loss while preserving
	the amounts approved during reconciliation.
	"""
	source_currency = manual_reconcile_amounts.get("source_currency")
	target_currency = manual_reconcile_amounts.get("target_currency")
	manual_cross_rate = flt(manual_reconcile_amounts.get("exchange_rate"), 9)
	if not source_currency or not target_currency or manual_cross_rate <= 0:
		return

	company_currency = payment_entry.company_currency or get_company_currency(payment_entry.company)
	currency_rates = {}

	if source_currency == company_currency:
		currency_rates[source_currency] = 1
		currency_rates[target_currency] = flt(1 / manual_cross_rate, 9)
	elif target_currency == company_currency:
		currency_rates[target_currency] = 1
		currency_rates[source_currency] = flt(manual_cross_rate, 9)
	else:
		source_to_company_rate = get_company_rate_for_currency(
			payment_entry=payment_entry,
			currency=source_currency,
			company_currency=company_currency,
			posting_date=bt.date,
		)
		currency_rates[source_currency] = source_to_company_rate
		currency_rates[target_currency] = flt(source_to_company_rate / manual_cross_rate, 9)

	if payment_entry.paid_from_account_currency in currency_rates:
		payment_entry.source_exchange_rate = currency_rates[payment_entry.paid_from_account_currency]

	if payment_entry.paid_to_account_currency in currency_rates:
		payment_entry.target_exchange_rate = currency_rates[payment_entry.paid_to_account_currency]


def get_company_rate_for_currency(
	payment_entry: "Document", currency: str, company_currency: str, posting_date
) -> float:
	"""Get a reliable currency-to-company rate for manual cross-rate derivation.

	Business context: when neither leg of a manual FX pair is the company
	currency, reconciliation still needs a company-currency anchor to calculate PE
	rates correctly. This helper prefers rates already present on the document and
	falls back to ERPNext's configured exchange-rate lookup for the posting date.
	"""
	if currency == company_currency:
		return 1

	if payment_entry.paid_from_account_currency == currency and flt(payment_entry.source_exchange_rate) > 0:
		return flt(payment_entry.source_exchange_rate, 9)

	if payment_entry.paid_to_account_currency == currency and flt(payment_entry.target_exchange_rate) > 0:
		return flt(payment_entry.target_exchange_rate, 9)

	rate = flt(get_exchange_rate(currency, company_currency, posting_date), 9)
	if rate <= 0:
		frappe.throw(
			_("Unable to determine exchange rate for {0} against {1}.").format(currency, company_currency)
		)

	return rate


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
