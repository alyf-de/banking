# Copyright (c) 2023, ALYF GmbH and contributors
# For license information, please see license.txt
import json
import datetime
from typing import Union

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.custom import ConstantColumn
from frappe.query_builder.functions import Coalesce
from frappe.utils import cint, flt, sbool

from erpnext import get_company_currency, get_default_cost_center
from erpnext.accounts.doctype.bank_transaction.bank_transaction import (
	BankTransaction,
	get_total_allocated_amount,
)
from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
	reconcile_vouchers,
)
from erpnext.accounts.utils import get_account_currency


class BankReconciliationToolBeta(Document):
	pass


@frappe.whitelist()
def get_bank_transactions(
	bank_account: str,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	order_by: str | datetime.date = "date asc",
):
	# returns bank transactions for a bank account
	filters = []
	filters.append(["bank_account", "=", bank_account])
	filters.append(["docstatus", "=", 1])
	filters.append(["unallocated_amount", ">", 0.0])
	if to_date:
		filters.append(["date", "<=", to_date])
	if from_date:
		filters.append(["date", ">=", from_date])
	transactions = frappe.get_all(
		"Bank Transaction",
		fields=[
			"date",
			"deposit",
			"withdrawal",
			"currency",
			"description",
			"name",
			"bank_account",
			"company",
			"unallocated_amount",
			"reference_number",
			"party_type",
			"party",
			"bank_party_name",
			"bank_party_account_number",
			"bank_party_iban",
		],
		filters=filters,
		order_by=order_by,
	)
	return transactions


@frappe.whitelist()
def create_journal_entry_bts(
	bank_transaction_name: str,
	reference_number: str = None,
	reference_date: str | datetime.date = None,
	posting_date: str | datetime.date = None,
	entry_type: str = None,
	second_account: str = None,
	mode_of_payment: str = None,
	party_type: str = None,
	party: str = None,
	allow_edit: bool | str = False,
):
	"""Create a new Journal Entry for Reconciling the Bank Transaction"""
	if isinstance(allow_edit, str):
		allow_edit = sbool(allow_edit)

	bank_transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)
	if bank_transaction.deposit and bank_transaction.withdrawal:
		frappe.throw(
			_(
				"Cannot create Journal Entry for a Bank Transaction with both Deposit and Withdrawal"
			)
		)

	bank_debit_amount = (
		bank_transaction.unallocated_amount if bank_transaction.deposit > 0.0 else 0.0
	)
	bank_credit_amount = (
		bank_transaction.unallocated_amount if bank_transaction.withdrawal > 0.0 else 0.0
	)

	company_account = frappe.get_value(
		"Bank Account", bank_transaction.bank_account, "account"
	)
	company, company_currency = frappe.get_value(
		"Account", company_account, ["company", "account_currency"]
	)

	second_account_type, second_account_currency = frappe.db.get_value(
		"Account", second_account, ["account_type", "account_currency"]
	)
	if second_account_type in ["Receivable", "Payable"] and not (party_type and party):
		frappe.throw(
			_("Party Type and Party is required for Receivable / Payable account {0}").format(
				second_account
			)
		)

	if second_account_currency != company_currency:
		frappe.throw(
			_(
				"The currency of the second account ({0}) must be the same as of the bank account ({1})"
			).format(second_account, company_currency)
		)

	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.update(
		{
			"voucher_type": entry_type,
			"company": company,
			"posting_date": posting_date,
			"cheque_date": reference_date,
			"cheque_no": reference_number,
			"mode_of_payment": mode_of_payment,
		}
	)
	journal_entry.set(
		"accounts",
		[
			{
				"account": second_account,
				"credit_in_account_currency": bank_debit_amount,
				"debit_in_account_currency": bank_credit_amount,
				"party_type": party_type,
				"party": party,
				"cost_center": get_default_cost_center(company),
			},
			{
				"account": company_account,
				"bank_account": bank_transaction.bank_account,
				"credit_in_account_currency": bank_credit_amount,
				"debit_in_account_currency": bank_debit_amount,
				"cost_center": get_default_cost_center(company),
			},
		],
	)
	journal_entry.insert()

	if allow_edit:
		return journal_entry  # Return saved document

	journal_entry.submit()

	return reconcile_voucher(
		bank_transaction_name,
		bank_transaction.unallocated_amount,
		"Journal Entry",
		journal_entry.name,
	)


@frappe.whitelist()
def create_payment_entry_bts(
	bank_transaction_name: str,
	reference_number: str = None,
	reference_date: str = None,
	party_type: str = None,
	party: str = None,
	posting_date: str = None,
	mode_of_payment: str = None,
	project: str = None,
	cost_center: str = None,
	allow_edit: bool = False,
):
	if isinstance(allow_edit, str):
		allow_edit = sbool(allow_edit)

	# Create a new payment entry based on the bank transaction
	bank_transaction = frappe.db.get_values(
		"Bank Transaction",
		bank_transaction_name,
		fieldname=["name", "unallocated_amount", "deposit", "bank_account"],
		as_dict=True,
	)[0]
	paid_amount = bank_transaction.unallocated_amount
	payment_type = "Receive" if bank_transaction.deposit > 0.0 else "Pay"

	company_account = frappe.get_value(
		"Bank Account", bank_transaction.bank_account, "account"
	)
	company = frappe.get_value("Account", company_account, "company")
	payment_entry_dict = {
		"company": company,
		"payment_type": payment_type,
		"reference_no": reference_number,
		"reference_date": reference_date,
		"party_type": party_type,
		"party": party,
		"posting_date": posting_date,
		"paid_amount": paid_amount,
		"received_amount": paid_amount,
	}
	payment_entry = frappe.new_doc("Payment Entry")

	payment_entry.update(payment_entry_dict)

	if mode_of_payment:
		payment_entry.mode_of_payment = mode_of_payment
	if project:
		payment_entry.project = project
	if cost_center:
		payment_entry.cost_center = cost_center
	if payment_type == "Receive":
		payment_entry.paid_to = company_account
	else:
		payment_entry.paid_from = company_account

	payment_entry.validate()
	payment_entry.insert()

	if allow_edit:
		return payment_entry  # Return saved document

	payment_entry.submit()

	return reconcile_voucher(
		bank_transaction_name, paid_amount, "Payment Entry", payment_entry.name
	)


@frappe.whitelist()
def bulk_reconcile_vouchers(
	bank_transaction_name: str,
	vouchers: str | list[dict],
	reconcile_multi_party: bool = False,
	account: str | None = None,
) -> "BankTransaction":
	"""
	Reconcile multiple vouchers with a bank transaction.

	:param vouchers: JSON string of vouchers to reconcile
	        structure: [
	                {
	                        "payment_doctype": "Payment Entry",
	                        "payment_name": "PE-00001",
	                        "amount": 1000.0,
	                        "party": "XYZ",
	                }
	        ]
	"""
	if isinstance(vouchers, str):
		vouchers = json.loads(vouchers)

	reconcile_multi_party = sbool(reconcile_multi_party)

	if reconcile_multi_party and not account:
		frappe.throw(_("An Account is required for multi-party reconciliation"))

	transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)
	transaction.add_payment_entries(vouchers, reconcile_multi_party, account)
	transaction.validate_duplicate_references()
	transaction.allocate_payment_entries()
	transaction.update_allocated_amount()
	transaction.set_status()
	transaction.save()

	return transaction


@frappe.whitelist()
def reconcile_voucher(
	transaction_name: str, amount: float, voucher_type: str, voucher_name: str
) -> Union[dict, "BankTransaction"]:
	"""Reconcile a entry with a bank transaction. Called on `doc_update` websocket event."""

	# Newly created voucher was deleted
	if not frappe.db.exists(voucher_type, voucher_name):
		return {"deleted": 1}

	# Newly created voucher was not submitted (saved)
	if not frappe.db.get_value(voucher_type, voucher_name, "docstatus") == 1:
		return {}

	vouchers = json.dumps(
		[
			{
				"payment_doctype": voucher_type,
				"payment_name": voucher_name,
				"amount": amount,
			}
		]
	)
	return reconcile_vouchers(transaction_name, vouchers)


@frappe.whitelist()
def upload_bank_statement(**args):
	args = frappe._dict(args)
	bsi = frappe.new_doc("Bank Statement Import")

	if args.company:
		bsi.update(
			{
				"company": args.company,
			}
		)

	if args.bank_account:
		bsi.update({"bank_account": args.bank_account})

	bsi.save()
	return bsi  # Return saved document


@frappe.whitelist()
def auto_reconcile_vouchers(
	bank_account: str,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	filter_by_reference_date: str | bool = False,
	from_reference_date: str | datetime.date = None,
	to_reference_date: str | datetime.date = None,
):
	# Auto reconcile vouchers with matching reference numbers
	frappe.flags.auto_reconcile_vouchers = True
	reconciled, partially_reconciled = set(), set()

	bank_transactions = get_bank_transactions(bank_account, from_date, to_date)
	for transaction in bank_transactions:
		linked_payments = get_linked_payments(
			transaction.name,
			["payment_entry", "journal_entry"],
			from_date,
			to_date,
			filter_by_reference_date,
			from_reference_date,
			to_reference_date,
		)

		if not linked_payments:
			continue

		vouchers = list(
			map(
				lambda entry: {
					"payment_doctype": entry.get("doctype"),
					"payment_name": entry.get("name"),
					"amount": entry.get("paid_amount"),
				},
				linked_payments,
			)
		)

		unallocated_before = transaction.unallocated_amount
		transaction = reconcile_vouchers(transaction.name, json.dumps(vouchers))

		if transaction.status == "Reconciled":
			reconciled.add(transaction.name)
		elif flt(unallocated_before) != flt(transaction.unallocated_amount):
			partially_reconciled.add(transaction.name)  # Partially reconciled

	alert_message, indicator = "", "blue"
	if not partially_reconciled and not reconciled:
		alert_message = _("No matches occurred via Auto Reconciliation")

	if reconciled:
		alert_message += _("{0} {1} {2}").format(
			len(reconciled),
			_("Transactions") if len(reconciled) > 1 else _("Transaction"),
			frappe.bold(_("Reconciled")),
		)
		alert_message += "<br>"
		indicator = "green"

	if partially_reconciled:
		alert_message += _("{0} {1} {2}").format(
			len(partially_reconciled),
			_("Transactions") if len(partially_reconciled) > 1 else _("Transaction"),
			frappe.bold(_("Partially Reconciled")),
		)
		indicator = "green"

	frappe.msgprint(
		title=_("Auto Reconciliation Complete"), msg=alert_message, indicator=indicator
	)
	frappe.flags.auto_reconcile_vouchers = False
	return reconciled, partially_reconciled


@frappe.whitelist()
def get_linked_payments(
	bank_transaction_name: str,
	document_types: str | list,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	filter_by_reference_date: str | bool = False,
	from_reference_date: str | datetime.date = None,
	to_reference_date: str | datetime.date = None,
) -> list:
	# get all matching payments for a bank transaction
	transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)
	gl_account, company = frappe.db.get_value(
		"Bank Account", transaction.bank_account, ["account", "company"]
	)

	if isinstance(document_types, str):
		document_types = json.loads(document_types)

	matching = check_matching(
		gl_account,
		company,
		transaction,
		document_types,
		from_date,
		to_date,
		sbool(filter_by_reference_date),
		from_reference_date,
		to_reference_date,
	)
	return subtract_allocations(gl_account, matching)


def subtract_allocations(gl_account, vouchers):
	"Look up & subtract any existing Bank Transaction allocations"
	copied = []
	for voucher in vouchers:
		rows = get_total_allocated_amount(voucher.get("doctype"), voucher.get("name"))
		amount = None
		for row in rows:
			if row["gl_account"] == gl_account:
				amount = row["total"]
				break

		if amount:
			voucher["paid_amount"] -= amount

		copied.append(voucher)
	return copied


def check_matching(
	bank_account: str,
	company: str,
	transaction: "BankTransaction",
	document_types: list,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	filter_by_reference_date: bool = False,
	from_reference_date: str | datetime.date = None,
	to_reference_date: str | datetime.date = None,
):
	common_filters = frappe._dict(
		amount=transaction.unallocated_amount,
		payment_type=("Receive" if transaction.deposit > 0.0 else "Pay"),
		reference_no=transaction.reference_number,
		party_type=transaction.party_type,
		party=transaction.party,
		bank_account=bank_account,
		date=transaction.date,
	)

	# combine all types of vouchers
	queries = get_queries(
		bank_account,
		company,
		transaction,
		document_types,
		from_date,
		to_date,
		filter_by_reference_date,
		from_reference_date,
		to_reference_date,
		common_filters,
	)

	matching_vouchers = []
	for query in queries:
		matching_vouchers.extend(query.run(as_dict=True))

	if not matching_vouchers:
		return []

	if transaction.description:
		for voucher in matching_vouchers:
			# higher rank if voucher name is in bank transaction
			reference_no = voucher["reference_no"]
			if reference_no and (reference_no.strip() in transaction.description):
				voucher["rank"] += 1
				voucher["name_in_desc_match"] = 1

	return sorted(matching_vouchers, key=lambda x: x["rank"], reverse=True)


def get_queries(
	bank_account: str,
	company: str,
	transaction: "BankTransaction",
	document_types: list,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	filter_by_reference_date: bool = False,
	from_reference_date: str | datetime.date = None,
	to_reference_date: str | datetime.date = None,
	common_filters: frappe._dict = None,
):
	# get queries to get matching vouchers
	account_from_to = "paid_to" if transaction.deposit > 0.0 else "paid_from"
	exact_match = "exact_match" in document_types
	queries = []

	# get matching queries from all the apps (except erpnext, to override)
	for method_name in frappe.get_hooks("get_matching_queries")[1:]:
		queries.extend(
			frappe.get_attr(method_name)(
				bank_account,
				company,
				transaction,
				document_types,
				exact_match,
				account_from_to,
				from_date,
				to_date,
				filter_by_reference_date,
				from_reference_date,
				to_reference_date,
				common_filters,
			)
			or []
		)

	return queries


def get_matching_queries(
	bank_account: str,
	company: str,
	transaction: "BankTransaction",
	document_types: list,
	exact_match: bool = False,
	account_from_to: str = None,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	filter_by_reference_date: bool = False,
	from_reference_date: str | datetime.date = None,
	to_reference_date: str | datetime.date = None,
	common_filters: frappe._dict = None,
):
	if not common_filters:
		common_filters = frappe._dict()

	queries = []
	currency = get_account_currency(bank_account)
	is_withdrawal = transaction.withdrawal > 0.0
	is_deposit = transaction.deposit > 0.0

	common_filters.exact_party_match = "exact_party_match" in (document_types or [])

	if "payment_entry" in document_types:
		query = get_pe_matching_query(
			exact_match,
			common_filters,
			account_from_to,
			from_date,
			to_date,
			filter_by_reference_date,
			from_reference_date,
			to_reference_date,
		)
		queries.append(query)

	if "journal_entry" in document_types:
		query = get_je_matching_query(
			exact_match,
			common_filters,
			from_date,
			to_date,
			filter_by_reference_date,
			from_reference_date,
			to_reference_date,
		)
		queries.append(query)

	# -- Invoices --
	include_unpaid = "unpaid_invoices" in document_types
	invoice_dt = "sales_invoice" if is_deposit else "purchase_invoice"
	invoice_queries_map = get_invoice_function_map(document_types, is_deposit)

	kwargs = frappe._dict(
		exact_match=exact_match,
		currency=currency,
		common_filters=common_filters,
	)
	if include_unpaid:
		kwargs.company = company
		for doctype, fn in invoice_queries_map.items():
			if doctype in ["sales_invoice", "purchase_invoice"]:
				kwargs.include_only_returns = doctype != invoice_dt
			elif kwargs.include_only_returns is not None:
				# Remove the key when doctype == "expense_claim"
				del kwargs.include_only_returns

			queries.append(fn(**kwargs))
	else:
		if fn := invoice_queries_map.get(invoice_dt):
			queries.append(fn(**kwargs))

	if "loan_disbursement" in document_types and is_withdrawal:
		queries.append(get_ld_matching_query(exact_match, common_filters))

	if "loan_repayment" in document_types and is_deposit:
		queries.append(get_lr_matching_query(exact_match, common_filters))

	if "bank_transaction" in document_types:
		query = get_bt_matching_query(exact_match, common_filters, transaction.name)
		queries.append(query)

	return queries


def get_bt_matching_query(
	exact_match: bool, common_filters: frappe._dict, transaction_name: str
):
	# get matching bank transaction query
	# find bank transactions in the same bank account with opposite sign
	# same bank account must have same company and currency
	bt = frappe.qb.DocType("Bank Transaction")
	field = "deposit" if common_filters.payment_type == "Pay" else "withdrawal"

	ref_rank = (
		frappe.qb.terms.Case()
		.when(bt.reference_number == common_filters.reference_no, 1)
		.else_(0)
	)
	unallocated_rank = (
		frappe.qb.terms.Case()
		.when(bt.unallocated_amount == common_filters.amount, 1)
		.else_(0)
	)

	amount_equality = getattr(bt, field) == common_filters.amount
	amount_rank = frappe.qb.terms.Case().when(amount_equality, 1).else_(0)

	party_condition = (
		(bt.party_type == common_filters.party_type)
		& (bt.party == common_filters.party)
		& bt.party.isnotnull()
	)
	party_rank = frappe.qb.terms.Case().when(party_condition, 1).else_(0)
	amount_condition = amount_equality if exact_match else getattr(bt, field) > 0.0

	query = (
		frappe.qb.from_(bt)
		.select(
			(ref_rank + amount_rank + party_rank + unallocated_rank + 1).as_("rank"),
			ConstantColumn("Bank Transaction").as_("doctype"),
			bt.name,
			bt.unallocated_amount.as_("paid_amount"),
			bt.reference_number.as_("reference_no"),
			bt.date.as_("reference_date"),
			bt.party,
			bt.party_type,
			bt.date.as_("posting_date"),
			bt.currency,
			ref_rank.as_("reference_number_match"),
			amount_rank.as_("amount_match"),
			party_rank.as_("party_match"),
			unallocated_rank.as_("unallocated_amount_match"),
		)
		.where(bt.status != "Reconciled")
		.where(bt.name != transaction_name)
		.where(bt.bank_account == common_filters.bank_account)
		.where(amount_condition)
		.where(bt.docstatus == 1)
	)

	if common_filters.exact_party_match:
		query = query.where(party_condition)

	return query


def get_ld_matching_query(exact_match: bool, common_filters: frappe._dict):
	loan_disbursement = frappe.qb.DocType("Loan Disbursement")
	matching_reference = loan_disbursement.reference_number == common_filters
	matching_party = (
		loan_disbursement.applicant_type == common_filters.party_type
		and loan_disbursement.applicant == common_filters.matching_party
	)

	date_condition = (
		Coalesce(loan_disbursement.reference_date, loan_disbursement.disbursement_date)
		== common_filters.date
	)
	date_rank = frappe.qb.terms.Case().when(date_condition, 1).else_(0)

	reference_rank = frappe.qb.terms.Case().when(matching_reference, 1).else_(0)
	party_rank = frappe.qb.terms.Case().when(matching_party, 1).else_(0)

	query = (
		frappe.qb.from_(loan_disbursement)
		.select(
			(reference_rank + party_rank + date_rank + 1).as_("rank"),
			ConstantColumn("Loan Disbursement").as_("doctype"),
			loan_disbursement.name,
			loan_disbursement.disbursed_amount.as_("paid_amount"),
			loan_disbursement.reference_number.as_("reference_no"),
			loan_disbursement.reference_date,
			loan_disbursement.applicant.as_("party"),
			loan_disbursement.applicant_type.as_("party_type"),
			loan_disbursement.disbursement_date.as_("posting_date"),
			ConstantColumn("").as_("currency"),
			reference_rank.as_("reference_number_match"),
			party_rank.as_("party_match"),
			date_rank.as_("date_match"),
		)
		.where(loan_disbursement.docstatus == 1)
		.where(loan_disbursement.clearance_date.isnull())
		.where(loan_disbursement.disbursement_account == common_filters.bank_account)
	)

	if exact_match:
		query.where(loan_disbursement.disbursed_amount == common_filters.amount)
	else:
		query.where(loan_disbursement.disbursed_amount > 0.0)

	return query


def get_lr_matching_query(exact_match: bool, common_filters: frappe._dict):
	loan_repayment = frappe.qb.DocType("Loan Repayment")
	matching_reference = loan_repayment.reference_number == common_filters.reference_no
	matching_party = (
		loan_repayment.applicant_type == common_filters.party_type
		and loan_repayment.applicant == common_filters.party
	)

	date_condition = (
		Coalesce(loan_repayment.reference_date, loan_repayment.posting_date)
		== common_filters.date
	)
	date_rank = frappe.qb.terms.Case().when(date_condition, 1).else_(0)

	reference_rank = frappe.qb.terms.Case().when(matching_reference, 1).else_(0)
	party_rank = frappe.qb.terms.Case().when(matching_party, 1).else_(0)

	query = (
		frappe.qb.from_(loan_repayment)
		.select(
			(reference_rank + party_rank + date_rank + 1).as_("rank"),
			ConstantColumn("Loan Repayment").as_("doctype"),
			loan_repayment.name,
			loan_repayment.amount_paid.as_("paid_amount"),
			loan_repayment.reference_number.as_("reference_no"),
			loan_repayment.reference_date,
			loan_repayment.applicant.as_("party"),
			loan_repayment.applicant_type.as_("party_type"),
			loan_repayment.posting_date,
			ConstantColumn("").as_("currency"),
			reference_rank.as_("reference_number_match"),
			party_rank.as_("party_match"),
			date_rank.as_("date_match"),
		)
		.where(loan_repayment.docstatus == 1)
		.where(loan_repayment.clearance_date.isnull())
		.where(loan_repayment.payment_account == common_filters.bank_account)
	)

	if frappe.db.has_column("Loan Repayment", "repay_from_salary"):
		query = query.where((loan_repayment.repay_from_salary == 0))

	if exact_match:
		query.where(loan_repayment.amount_paid == common_filters.amount)
	else:
		query.where(loan_repayment.amount_paid > 0.0)

	return query


def get_pe_matching_query(
	exact_match: bool,
	common_filters: frappe._dict,
	account_from_to: str,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	filter_by_reference_date: bool = False,
	from_reference_date: str | datetime.date = None,
	to_reference_date: str | datetime.date = None,
):
	to_from = "to" if common_filters.payment_type == "Receive" else "from"
	currency_field = f"paid_{to_from}_account_currency"
	payment_type = common_filters.payment_type
	pe = frappe.qb.DocType("Payment Entry")

	ref_condition = pe.reference_no == common_filters.reference_no
	ref_rank = frappe.qb.terms.Case().when(ref_condition, 1).else_(0)

	amount_equality = pe.paid_amount == common_filters.amount
	amount_rank = frappe.qb.terms.Case().when(amount_equality, 1).else_(0)
	amount_condition = amount_equality if exact_match else pe.paid_amount > 0.0

	party_condition = (
		(pe.party_type == common_filters.party_type)
		& (pe.party == common_filters.party)
		& pe.party.isnotnull()
	)
	party_rank = frappe.qb.terms.Case().when(party_condition, 1).else_(0)

	filter_by_date = pe.posting_date.between(from_date, to_date)
	if cint(filter_by_reference_date):
		filter_by_date = pe.reference_date.between(from_reference_date, to_reference_date)

	date_condition = Coalesce(pe.reference_date, pe.posting_date) == common_filters.date
	date_rank = frappe.qb.terms.Case().when(date_condition, 1).else_(0)

	query = (
		frappe.qb.from_(pe)
		.select(
			(ref_rank + amount_rank + party_rank + date_rank + 1).as_("rank"),
			ConstantColumn("Payment Entry").as_("doctype"),
			pe.name,
			pe.paid_amount,
			pe.reference_no,
			pe.reference_date,
			pe.party,
			pe.party_name,
			pe.party_type,
			pe.posting_date,
			getattr(pe, currency_field).as_("currency"),
			ref_rank.as_("reference_number_match"),
			amount_rank.as_("amount_match"),
			party_rank.as_("party_match"),
			date_rank.as_("date_match"),
		)
		.where(pe.docstatus == 1)
		.where(pe.payment_type.isin([payment_type, "Internal Transfer"]))
		.where(pe.clearance_date.isnull())
		.where(getattr(pe, account_from_to) == common_filters.bank_account)
		.where(amount_condition)
		.where(filter_by_date)
		.orderby(pe.reference_date if cint(filter_by_reference_date) else pe.posting_date)
	)

	if frappe.flags.auto_reconcile_vouchers:
		query = query.where(ref_condition)
	if common_filters.exact_party_match:
		query = query.where(party_condition)

	return query


def get_je_matching_query(
	exact_match: bool,
	common_filters: frappe._dict,
	from_date: str | datetime.date = None,
	to_date: str | datetime.date = None,
	filter_by_reference_date: bool = False,
	from_reference_date: str | datetime.date = None,
	to_reference_date: str | datetime.date = None,
):
	# get matching journal entry query
	# We have mapping at the bank level
	# So one bank could have both types of bank accounts like asset and liability
	# So cr_or_dr should be judged only on basis of withdrawal and deposit and not account type
	cr_or_dr = "credit" if common_filters.payment_type == "Pay" else "debit"
	je = frappe.qb.DocType("Journal Entry")
	jea = frappe.qb.DocType("Journal Entry Account")

	ref_condition = je.cheque_no == common_filters.reference_no
	ref_rank = frappe.qb.terms.Case().when(ref_condition, 1).else_(0)

	amount_field = f"{cr_or_dr}_in_account_currency"
	amount_equality = getattr(jea, amount_field) == common_filters.amount
	amount_rank = frappe.qb.terms.Case().when(amount_equality, 1).else_(0)

	filter_by_date = je.posting_date.between(from_date, to_date)
	if cint(filter_by_reference_date):
		filter_by_date = je.cheque_date.between(from_reference_date, to_reference_date)

	date_condition = Coalesce(je.cheque_date, je.posting_date) == common_filters.date
	date_rank = frappe.qb.terms.Case().when(date_condition, 1).else_(0)

	query = (
		frappe.qb.from_(jea)
		.join(je)
		.on(jea.parent == je.name)
		.select(
			(ref_rank + amount_rank + date_rank + 1).as_("rank"),
			ConstantColumn("Journal Entry").as_("doctype"),
			je.name,
			getattr(jea, amount_field).as_("paid_amount"),
			je.cheque_no.as_("reference_no"),
			je.cheque_date.as_("reference_date"),
			je.pay_to_recd_from.as_("party"),
			jea.party_type,
			je.posting_date,
			jea.account_currency.as_("currency"),
			ref_rank.as_("reference_number_match"),
			amount_rank.as_("amount_match"),
			date_rank.as_("date_match"),
		)
		.where(je.docstatus == 1)
		.where(je.voucher_type != "Opening Entry")
		.where(je.clearance_date.isnull())
		.where(jea.account == common_filters.bank_account)
		.where(amount_equality if exact_match else getattr(jea, amount_field) > 0.0)
		.where(je.docstatus == 1)
		.where(filter_by_date)
		.orderby(je.cheque_date if cint(filter_by_reference_date) else je.posting_date)
	)

	if frappe.flags.auto_reconcile_vouchers:
		query = query.where(ref_condition)

	return query


def get_si_matching_query(
	exact_match: bool, currency: str, common_filters: frappe._dict
):
	"""
	Get matching sales invoices when they are also used as payment entries (POS).
	"""
	si = frappe.qb.DocType("Sales Invoice")
	sip = frappe.qb.DocType("Sales Invoice Payment")

	amount_equality = sip.amount == common_filters.amount
	amount_rank = frappe.qb.terms.Case().when(amount_equality, 1).else_(0)
	amount_condition = amount_equality if exact_match else sip.amount != 0.0

	party_condition = si.customer == common_filters.party
	party_rank = frappe.qb.terms.Case().when(party_condition, 1).else_(0)

	date_condition = si.posting_date == common_filters.date
	date_rank = frappe.qb.terms.Case().when(date_condition, 1).else_(0)

	query = (
		frappe.qb.from_(sip)
		.join(si)
		.on(sip.parent == si.name)
		.select(
			(party_rank + amount_rank + date_rank + 1).as_("rank"),
			ConstantColumn("Sales Invoice").as_("doctype"),
			si.name,
			sip.amount.as_("paid_amount"),
			si.name.as_("reference_no"),
			si.posting_date.as_("reference_date"),
			si.customer.as_("party"),
			ConstantColumn("Customer").as_("party_type"),
			si.posting_date,
			si.currency,
			party_rank.as_("party_match"),
			amount_rank.as_("amount_match"),
			date_rank.as_("date_match"),
		)
		.where(si.docstatus == 1)
		.where(sip.clearance_date.isnull())
		.where(sip.account == common_filters.bank_account)
		.where(amount_condition)
		.where(si.currency == currency)
	)

	if common_filters.exact_party_match:
		query = query.where(party_condition)

	return query


def get_unpaid_si_matching_query(
	exact_match: bool,
	currency: str,
	common_filters: frappe._dict,
	company: str,
	include_only_returns: bool = False,
):
	sales_invoice = frappe.qb.DocType("Sales Invoice")

	party_condition = sales_invoice.customer == common_filters.party
	party_match = frappe.qb.terms.Case().when(party_condition, 1).else_(0)

	outstanding_amount_condition = (
		sales_invoice.outstanding_amount == common_filters.amount
	)
	amount_match = frappe.qb.terms.Case().when(outstanding_amount_condition, 1).else_(0)

	query = (
		frappe.qb.from_(sales_invoice)
		.select(
			(party_match + amount_match + 1).as_("rank"),
			ConstantColumn("Sales Invoice").as_("doctype"),
			sales_invoice.name.as_("name"),
			sales_invoice.outstanding_amount.as_("paid_amount"),
			sales_invoice.name.as_("reference_no"),
			sales_invoice.posting_date.as_("reference_date"),
			sales_invoice.customer.as_("party"),
			ConstantColumn("Customer").as_("party_type"),
			sales_invoice.customer_name.as_("party_name"),
			sales_invoice.posting_date,
			sales_invoice.currency,
			party_match.as_("party_match"),
			amount_match.as_("amount_match"),
		)
		.where(sales_invoice.docstatus == 1)
		.where(sales_invoice.company == company)  # because we do not have bank account check
		.where(sales_invoice.outstanding_amount != 0.0)
		.where(sales_invoice.currency == currency)
	)

	if include_only_returns:
		query = query.where(sales_invoice.is_return == 1)
	if exact_match:
		query = query.where(outstanding_amount_condition)
	if common_filters.exact_party_match:
		query = query.where(party_condition)

	return query


def get_pi_matching_query(
	exact_match: bool, currency: str, common_filters: frappe._dict
):
	"""
	Get matching purchase invoice query when they are also used as payment entries (is_paid)
	"""
	purchase_invoice = frappe.qb.DocType("Purchase Invoice")

	amount_equality = purchase_invoice.paid_amount == common_filters.amount
	amount_rank = frappe.qb.terms.Case().when(amount_equality, 1).else_(0)
	amount_condition = (
		amount_equality if exact_match else purchase_invoice.paid_amount != 0.0
	)

	party_condition = purchase_invoice.supplier == common_filters.party
	party_rank = frappe.qb.terms.Case().when(party_condition, 1).else_(0)

	# date of BT and paid PI could be the same (date of payment or the date of the bill)
	date_condition = (
		Coalesce(purchase_invoice.bill_date, purchase_invoice.posting_date)
		== common_filters.date
	)
	date_rank = frappe.qb.terms.Case().when(date_condition, 1).else_(0)

	query = (
		frappe.qb.from_(purchase_invoice)
		.select(
			(party_rank + amount_rank + date_rank + 1).as_("rank"),
			ConstantColumn("Purchase Invoice").as_("doctype"),
			purchase_invoice.name,
			purchase_invoice.paid_amount,
			purchase_invoice.bill_no.as_("reference_no"),
			purchase_invoice.bill_date.as_("reference_date"),
			purchase_invoice.supplier.as_("party"),
			ConstantColumn("Supplier").as_("party_type"),
			purchase_invoice.supplier_name.as_("party_name"),
			purchase_invoice.posting_date,
			purchase_invoice.currency,
			party_rank.as_("party_match"),
			amount_rank.as_("amount_match"),
			date_rank.as_("date_match"),
		)
		.where(purchase_invoice.docstatus == 1)
		.where(purchase_invoice.is_paid == 1)
		.where(purchase_invoice.clearance_date.isnull())
		.where(purchase_invoice.cash_bank_account == common_filters.bank_account)
		.where(amount_condition)
		.where(purchase_invoice.currency == currency)
	)

	if common_filters.exact_party_match:
		query = query.where(party_condition)

	return query


def get_unpaid_pi_matching_query(
	exact_match: bool,
	currency: str,
	common_filters: frappe._dict,
	company: str,
	include_only_returns: bool = False,
):
	purchase_invoice = frappe.qb.DocType("Purchase Invoice")

	party_condition = purchase_invoice.supplier == common_filters.party
	party_match = frappe.qb.terms.Case().when(party_condition, 1).else_(0)

	outstanding_amount_condition = (
		purchase_invoice.outstanding_amount == common_filters.amount
	)
	amount_match = frappe.qb.terms.Case().when(outstanding_amount_condition, 1).else_(0)

	# We skip date rank as the date of an unpaid bill is mostly
	# earlier than the date of the bank transaction
	query = (
		frappe.qb.from_(purchase_invoice)
		.select(
			(party_match + amount_match + 1).as_("rank"),
			ConstantColumn("Purchase Invoice").as_("doctype"),
			purchase_invoice.name.as_("name"),
			purchase_invoice.outstanding_amount.as_("paid_amount"),
			purchase_invoice.bill_no.as_("reference_no"),
			purchase_invoice.bill_date.as_("reference_date"),
			purchase_invoice.supplier.as_("party"),
			ConstantColumn("Supplier").as_("party_type"),
			purchase_invoice.supplier_name.as_("party_name"),
			purchase_invoice.posting_date,
			purchase_invoice.currency,
			party_match.as_("party_match"),
			amount_match.as_("amount_match"),
		)
		.where(purchase_invoice.docstatus == 1)
		.where(purchase_invoice.company == company)
		.where(purchase_invoice.outstanding_amount != 0.0)
		.where(purchase_invoice.is_paid == 0)
		.where(purchase_invoice.currency == currency)
	)

	if include_only_returns:
		query = query.where(purchase_invoice.is_return == 1)
	if exact_match:
		query = query.where(outstanding_amount_condition)
	if common_filters.exact_party_match:
		query = query.where(party_condition)

	return query


def get_unpaid_ec_matching_query(
	exact_match: bool, currency: str, common_filters: frappe._dict, company: str
):
	if currency != get_company_currency(company):
		# Expense claims are always in company currency
		return ""

	expense_claim = frappe.qb.DocType("Expense Claim")

	party_condition = expense_claim.employee == common_filters.party
	party_match = frappe.qb.terms.Case().when(party_condition, 1).else_(0)

	outstanding_amount = (
		expense_claim.total_sanctioned_amount
		+ expense_claim.total_taxes_and_charges
		- expense_claim.total_amount_reimbursed
		- expense_claim.total_advance_amount
	)
	outstanding_amount_condition = outstanding_amount == common_filters.amount
	amount_match = frappe.qb.terms.Case().when(outstanding_amount_condition, 1).else_(0)

	query = (
		frappe.qb.from_(expense_claim)
		.select(
			(party_match + amount_match + 1).as_("rank"),
			ConstantColumn("Expense Claim").as_("doctype"),
			expense_claim.name.as_("name"),
			outstanding_amount.as_("paid_amount"),
			expense_claim.name.as_("reference_no"),
			expense_claim.posting_date.as_("reference_date"),
			expense_claim.employee.as_("party"),
			ConstantColumn("Employee").as_("party_type"),
			expense_claim.employee_name.as_("party_name"),
			expense_claim.posting_date,
			ConstantColumn(currency).as_("currency"),
			party_match.as_("party_match"),
			amount_match.as_("amount_match"),
		)
		.where(expense_claim.docstatus == 1)
		.where(expense_claim.company == company)
		.where(outstanding_amount > 0.0)
		.where(expense_claim.status == "Unpaid")
	)

	if exact_match:
		query = query.where(outstanding_amount_condition)
	if common_filters.exact_party_match:
		query = query.where(party_condition)

	return query


def get_invoice_function_map(document_types: list, is_deposit: bool):
	"""Get the function map for invoices based on the given filters."""
	include_unpaid = "unpaid_invoices" in document_types
	fn_map = {
		"sales_invoice": (
			get_unpaid_si_matching_query if include_unpaid else get_si_matching_query
		),
		"purchase_invoice": (
			get_unpaid_pi_matching_query if include_unpaid else get_pi_matching_query
		),
		"expense_claim": (
			get_unpaid_ec_matching_query if (include_unpaid and not is_deposit) else None
		),
	}
	order = (
		["sales_invoice", "purchase_invoice"]
		if (is_deposit)
		else ["purchase_invoice", "expense_claim", "sales_invoice"]
	)

	# Return the ordered function map that has a function and is in the document types
	return {
		doctype: fn_map[doctype]
		for doctype in order
		if (doctype in document_types and fn_map[doctype])
	}
