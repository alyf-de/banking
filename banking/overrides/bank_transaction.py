import json

import frappe
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction
from frappe import _
from frappe.core.utils import find
from frappe.utils import flt, getdate
from frappe.utils.data import evaluate_filters


class CustomBankTransaction(BankTransaction):
	def add_payment_entries(self, vouchers: list, reconcile_multi_party: bool = False):
		"Add the vouchers with zero allocation. Save() will perform the allocations and clearance"
		if self.unallocated_amount <= 0.0:
			frappe.throw(frappe._("Bank Transaction {0} is already fully reconciled").format(self.name))

		pe_length_before = len(self.payment_entries)
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
			"period_end_date",
			order_by="period_end_date desc",
		)
		if latest_period_close_date and getdate(self.date) <= getdate(latest_period_close_date):
			frappe.throw(
				_(
					"Due to Period Closing, you cannot reconcile unpaid vouchers with a Bank Transaction before {0}"
				).format(frappe.format(latest_period_close_date, "Date"))
			)

	def reconcile_paid_vouchers(self, vouchers):
		"""Reconcile paid vouchers with the Bank Transaction."""
		for voucher in vouchers:
			voucher_type, voucher_name = voucher["payment_doctype"], voucher["payment_name"]
			if self.is_duplicate_reference(voucher_type, voucher_name):
				continue

			self.append(
				"payment_entries",
				{
					"payment_document": voucher["payment_doctype"],
					"payment_entry": voucher["payment_name"],
					"allocated_amount": 0.0,  # Temporary
				},
			)

	def is_duplicate_reference(self, voucher_type, voucher_name):
		"""Check if the reference is already added to the Bank Transaction."""
		return find(
			self.payment_entries,
			lambda x: x.payment_document == voucher_type and x.payment_entry == voucher_name,
		)


def before_validate(doc, method):
	ensure_positive_deposit_withdrawal_fees(doc, method)


def before_submit(doc, method):
	date = doc.date or frappe.utils.nowdate()

	if not doc.bank_account:
		frappe.throw(_("No bank account - verify data!"))

	if doc.deposit == 0 and doc.withdrawal == 0:
		return

	if doc.deposit < 0 or doc.withdrawal < 0:
		frappe.throw(_("Debit or Credit is negative. Verify input data!"))

	# Generic data catching
	# Get Company
	company_doc = frappe.get_cached_doc("Company", doc.company)

	# Bank account debit/credit
	account = frappe.db.get_value("Bank Account", doc.bank_account, "account")
	# End Generic data catching

	# Set initial values
	debit, credit = (doc.deposit, 0) if doc.deposit > 0 else (0, doc.withdrawal)

	doc = create_je_bank_fees(doc, company_doc, date, account, debit, credit)
	doc = create_je_automatic_rules(doc, company_doc, date, account, debit, credit)


def on_update_after_submit(doc, event):
	"""Validate if the Bank Transaction is over-allocated."""
	to_allocate = flt(doc.withdrawal or doc.deposit)
	for entry in doc.payment_entries:
		to_allocate -= flt(entry.allocated_amount)
		if round(to_allocate, 2) < 0.0:
			symbol = frappe.db.get_value("Currency", doc.currency, "symbol")
			frappe.throw(
				msg=_("The Bank Transaction is over-allocated by {0} at row {1}.").format(
					frappe.bold(f"{symbol} {abs(to_allocate)!s}"), frappe.bold(entry.idx)
				),
				title=_("Over Allocation"),
			)


def on_cancel(doc, method):
	# Cancel the journal entries created by this Bank Transaction
	auto_created_journal_entries = frappe.get_all(
		"Journal Entry",
		filters={"cheque_no": doc.name},
		pluck="name",
	)

	for journal_entry in auto_created_journal_entries:
		try:
			doc = frappe.get_doc("Journal Entry", journal_entry)
			if doc.docstatus == 1:
				doc.cancel()
		except Exception as e:
			frappe.msgprint(_("Failed to cancel {0}: {1}").format(journal_entry, e))


def create_je_bank_fees(doc, company_doc, date, account, debit, credit):
	# First step: Create a journal entry for included bank fees
	included_fee = doc.included_fee

	if included_fee <= 0:
		return

	bank_fee_account = frappe.db.get_value("Bank Account", doc.bank_account, "bank_fee_account")
	if not bank_fee_account:
		frappe.throw(_("Please set the bank fee account in the bank account."))

	# only correct the credit value if set, as the debit value (deposit) is never including the fee.
	if credit > 0:
		credit = credit - included_fee
	if debit > 0:
		debit = debit - included_fee
	je_fee_name = create_automatic_journal_entry(
		doc, company_doc, date, account, bank_fee_account, None, 0, included_fee
	)
	doc.append(
		"payment_entries",
		{
			"payment_document": "Journal Entry",
			"payment_entry": je_fee_name,
			"allocated_amount": included_fee,
		},
	)
	# Set manually the un-/allocated amounts, as this value is already set and needs to be updated
	doc.allocated_amount = included_fee
	doc.unallocated_amount = debit + credit
	if doc.unallocated_amount == 0:
		doc.status = "Reconciled"

	return doc


def create_je_automatic_rules(doc, company_doc, date, account, debit, credit):
	# Second step: Automatic reconcilation based on the Bank Reconciliation Rules
	bank_reconciliation_rules = frappe.db.get_list(
		"Bank Reconciliation Rule",
		filters={
			"disabled": 0,
			"bank_account": doc.bank_account,
			"docstatus": 1,
		},
		fields=["name", "target_account", "filters"],
		as_list=True,
	)
	for br_rule in bank_reconciliation_rules:
		# Check if line matches filter
		if br_rule[2]:
			filters = json.loads(br_rule[2])
			if filters:
				condition_met = evaluate_filters(doc, filters)
				if condition_met:
					rule = br_rule[0]
					target_account = br_rule[1]
					je_auto_name = create_automatic_journal_entry(
						doc, company_doc, date, account, target_account, rule, debit, credit
					)
					doc.append(
						"payment_entries",
						{
							"payment_document": "Journal Entry",
							"payment_entry": je_auto_name,
							"allocated_amount": debit + credit,
						},
					)
					# Set manually the un-/allocated amounts, as this value is already set and needs to be updated
					doc.allocated_amount = doc.allocated_amount + debit + credit
					# Set remaining debit and credit to 0, so no cash in transit is generated
					debit = 0
					credit = 0
					doc.unallocated_amount = 0
					doc.status = "Reconciled"
					break

	return doc


def create_automatic_journal_entry(
	doc, company_doc, date, account, target_account, rule=None, debit=0, credit=0
):
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Journal Entry"
	journal_entry.posting_date = date
	journal_entry.company = doc.company
	rule_part = " " + _("by automatic rule {0}").format(rule) if rule else ""
	journal_entry.user_remark = _("Auto-created from BT: {0}").format(doc.name) + rule_part
	journal_entry.cheque_no = doc.name
	journal_entry.cheque_date = date
	journal_entry.multi_currency = 1
	journal_entry.clearance_date = frappe.utils.today()

	# Bank account entry
	journal_entry.append(
		"accounts",
		{
			"account": account,
			"bank_account": doc.bank_account,
			"debit_in_account_currency": debit,
			"credit_in_account_currency": credit,
			"cost_center": company_doc.cost_center,
		},
	)

	# Target account entry
	journal_entry.append(
		"accounts",
		{
			"account": target_account,
			"bank_account": "",
			"debit_in_account_currency": credit,
			"credit_in_account_currency": debit,
			"cost_center": company_doc.cost_center,
		},
	)

	journal_entry.submit()

	return journal_entry.name


def ensure_positive_deposit_withdrawal_fees(doc, method):
	doc.deposit = abs(flt(doc.deposit) or 0.0)
	doc.withdrawal = abs(flt(doc.withdrawal) or 0.0)
	doc.included_fee = abs(flt(doc.included_fee) or 0.0)
	doc.excluded_fee = abs(flt(doc.excluded_fee) or 0.0)
	# Re-call this function as the original function runs before this one and values are not converted
	BankTransaction.handle_excluded_fee(doc)
