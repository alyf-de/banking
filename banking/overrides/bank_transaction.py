import json

import frappe
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry
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


def before_validate(doc, method):
	ensure_positive_deposit_withdrawal_fees(doc)


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
			frappe.msgprint(f"Failed to cancel {journal_entry}: {e}")


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
	# Create a journal entry for the bank fees
	if doc.bank_account:
		bank_fee_account = frappe.db.get_value("Bank Account", doc.bank_account, "bank_fee_account")
		if not bank_fee_account:
			frappe.throw(_("Please set the bank fee account in the bank account."))

		# First Step: Book visible bank fees
		if doc.included_fee > 0 and bank_fee_account:
			included_fee = doc.included_fee
			# only correct the credit value if set, as the debit value (deposit) is never including the fee.
			if credit > 0:
				credit = credit - included_fee
			if debit > 0:
				debit = debit - included_fee
			je_fee_name = create_fee_journal_entry(
				doc, company_doc, date, account, bank_fee_account, included_fee
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
		else:
			included_fee = 0

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

	if debit == 0 and credit == 0:
		return

	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Bank Entry"
	journal_entry.title = f"BT ID {doc.name}"
	journal_entry.posting_date = date
	journal_entry.company = doc.company
	journal_entry.user_remark = f"Auto-created from BT: {doc.name}"
	journal_entry.cheque_no = doc.name
	journal_entry.cheque_date = date
	journal_entry.multi_currency = 1
	journal_entry.clearance_date = frappe.utils.today()

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

	# If by any filter, no accounting entries (single lines) are present, do not create a journal entry.
	if len(journal_entry.accounts) > 0:
		journal_entry.insert()

		# Create Exchange Gain/Loss Line
		JournalEntry.get_balance(journal_entry, difference_account=company_doc.exchange_gain_loss_account)

		journal_entry.submit()

	else:
		frappe.msgprint(
			_("No journal entry was created, as no data was present in the Accounting Entries table.")
		)


def create_automatic_journal_entry(doc, company_doc, date, account, target_account, rule, debit, credit):
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Journal Entry"
	journal_entry.title = f"BT ID {doc.name}"
	journal_entry.posting_date = date
	journal_entry.company = doc.company
	journal_entry.user_remark = f"Auto-created from BT: {doc.name} by automatic rule {rule}"
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


def create_fee_journal_entry(doc, company_doc, date, account, bank_fee_account, included_fee):
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Journal Entry"
	journal_entry.title = f"BT ID {doc.name}"
	journal_entry.posting_date = date
	journal_entry.company = doc.company
	journal_entry.user_remark = f"Auto-created from BT: {doc.name}"
	journal_entry.cheque_no = doc.name
	journal_entry.cheque_date = date
	journal_entry.multi_currency = 1
	journal_entry.clearance_date = frappe.utils.today()

	# Bank fee entry
	journal_entry.append(
		"accounts",
		{
			"account": account,
			"bank_account": doc.bank_account,
			"debit_in_account_currency": 0,
			"credit_in_account_currency": included_fee,
			"cost_center": company_doc.cost_center,
		},
	)

	# Fee account entry
	journal_entry.append(
		"accounts",
		{
			"account": bank_fee_account,
			"bank_account": "",
			"debit_in_account_currency": included_fee,
			"credit_in_account_currency": 0,
			"cost_center": company_doc.cost_center,
		},
	)

	journal_entry.submit()

	return journal_entry.name


def ensure_positive_deposit_withdrawal_fees(doc):
	doc.deposit = abs(flt(doc.deposit) or 0.0)
	doc.withdrawal = abs(flt(doc.withdrawal) or 0.0)
	doc.included_fee = abs(flt(doc.included_fee) or 0.0)
	doc.excluded_fee = abs(flt(doc.excluded_fee) or 0.0)
