import json

import frappe
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction
from frappe import _
from frappe.core.utils import find
from frappe.utils import flt, getdate
from frappe.utils.data import evaluate_filters, get_link_to_form


class CustomBankTransaction(BankTransaction):
	def add_payment_entries(self, vouchers: list, reconcile_multi_party: bool = False):
		"Add the vouchers with zero allocation. Save() will perform the allocations and clearance"
		if self.unallocated_amount <= 0.0:
			frappe.throw(
				_("{0} is already fully reconciled").format(get_link_to_form("Bank Transaction", self.name))
			)

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

	def convert_to_positive_value(self, fieldname: str):
		cur_value = self.get(fieldname)
		if cur_value is not None and flt(cur_value) < 0:
			self.set(fieldname, abs(flt(cur_value)))


def before_validate(doc: "CustomBankTransaction", method):
	enforce_positive_values(doc)


def before_submit(doc: "CustomBankTransaction", method):
	date = doc.date or frappe.utils.nowdate()

	if not doc.bank_account:
		frappe.throw(
			_("The field {0} is required. Please verify the input data.").format(
				_(doc.meta.get_label("bank_account"))
			)
		)

	if doc.deposit == 0 and doc.withdrawal == 0:
		return

	for fieldname in ["deposit", "withdrawal", "included_fee"]:
		value = doc.get(fieldname)
		if value is None:
			continue

		if value < 0:
			frappe.throw(
				_("The field {0} is negative. Please verify the input data.").format(
					_(doc.meta.get_label(fieldname))
				)
			)

	cost_center = frappe.get_cached_value("Company", doc.company, "cost_center")
	account = frappe.get_cached_value("Bank Account", doc.bank_account, "account")
	debit, credit = (doc.deposit, 0) if doc.deposit else (0, doc.withdrawal)
	included_fee = doc.included_fee or 0

	create_je_bank_fees(doc, cost_center, date, account, debit, credit)
	credit_no_fee = max(0, credit - included_fee)
	create_je_automatic_rules(doc, cost_center, date, account, debit, credit_no_fee)


def on_update_after_submit(doc, event):
	"""Validate if the Bank Transaction is over-allocated."""
	to_allocate = flt(doc.withdrawal or doc.deposit)
	for entry in doc.payment_entries:
		to_allocate -= flt(entry.allocated_amount)
		if round(to_allocate, 2) < 0.0:
			frappe.throw(
				msg=_("{0} is over-allocated by {1} at row {2}.").format(
					get_link_to_form("Bank Transaction", doc.name),
					frappe.bold(frappe.format(abs(to_allocate), "Currency", currency=doc.currency)),
					frappe.bold(entry.idx),
				),
				title=_("Over-allocation"),
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
			frappe.msgprint(
				_("Failed to cancel {0}: {1}").format(get_link_to_form("Journal Entry", journal_entry), e)
			)


def create_je_bank_fees(doc, cost_center, date, account, debit, credit):
	# First step: Create a journal entry for included bank fees
	included_fee = doc.included_fee

	if included_fee is None or included_fee <= 0:
		return

	bank_fee_account = frappe.db.get_value("Bank Account", doc.bank_account, "bank_fee_account")
	if not bank_fee_account:
		frappe.throw(
			_("Please specify a <i>Bank Fee Account</i> for {0}.").format(
				get_link_to_form("Bank Account", doc.bank_account)
			)
		)

	je_fee_name = create_automatic_journal_entry(
		company=doc.company,
		bank_account=doc.bank_account,
		bank_transaction=doc.name,
		cost_center=cost_center,
		date=date,
		account=account,
		target_account=bank_fee_account,
		debit=0,
		credit=included_fee,
	)

	if credit > 0:
		# only correct the credit value if set, as the debit value (deposit) is never including the fee.
		credit_no_fee = credit - included_fee
		# Set manually the un-/allocated amounts, as this value is already set and needs to be updated
		doc.allocated_amount = included_fee
		doc.unallocated_amount = debit + (credit_no_fee or 0)
		allocated_amount = included_fee
	else:
		allocated_amount = 0

	# Add the journal entry for a deposit fee with an allocated_amount of 0, as the fee is not included in the deposit itself.
	# Otherwise this would cause the un-/allocated amounts to fail.
	doc.append(
		"payment_entries",
		{
			"payment_document": "Journal Entry",
			"payment_entry": je_fee_name,
			"allocated_amount": allocated_amount,
		},
	)

	if doc.unallocated_amount == 0:
		doc.status = "Reconciled"


def create_je_automatic_rules(doc, cost_center, date, account, debit, credit):
	# Second step: Automatic reconcilation based on the Bank Reconciliation Rules
	bank_reconciliation_rules = frappe.get_all(
		"Bank Reconciliation Rule",
		filters={
			"disabled": 0,
			"bank_account": doc.bank_account,
			"docstatus": 1,
			"filters": ("is", "set"),
		},
		fields=["name", "target_account", "filters"],
		as_list=True,
	)

	for br_rule_name, target_account, filters in bank_reconciliation_rules:
		try:
			filters = json.loads(filters)
		except json.JSONDecodeError:
			frappe.log_error(
				title="Invalid Filters in Bank Reconciliation Rule",
				message=f"The filters for the Bank Reconciliation Rule {br_rule_name} are not valid JSON: {filters}",
				reference_doctype="Bank Reconciliation Rule",
				reference_name=br_rule_name,
			)
			continue

		if not evaluate_filters(doc, filters):
			continue

		je_auto_name = create_automatic_journal_entry(
			company=doc.company,
			bank_account=doc.bank_account,
			bank_transaction=doc.name,
			cost_center=cost_center,
			date=date,
			account=account,
			target_account=target_account,
			debit=debit,
			credit=credit,
			rule=br_rule_name,
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


def create_automatic_journal_entry(
	company: str,
	bank_account: str,
	bank_transaction: str,
	cost_center: str,
	date: str,
	account: str,
	target_account: str,
	debit: float = 0,
	credit: float = 0,
	rule: str | None = None,
):
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Journal Entry"
	journal_entry.posting_date = date
	journal_entry.company = company
	journal_entry.user_remark = (
		_("Auto-created from Bank Transaction {0} by Bank Reconciliation Rule {1}").format(
			bank_transaction, rule
		)
		if rule
		else _("Auto-created from Bank Transaction {0}").format(bank_transaction)
	)
	journal_entry.cheque_no = bank_transaction
	journal_entry.cheque_date = date
	journal_entry.multi_currency = 1

	# Bank account entry
	journal_entry.append(
		"accounts",
		{
			"account": account,
			"bank_account": bank_account,
			"debit_in_account_currency": debit,
			"credit_in_account_currency": credit,
			"cost_center": cost_center,
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
			"cost_center": cost_center,
		},
	)

	journal_entry.submit()
	frappe.db.set_value("Journal Entry", journal_entry.name, "clearance_date", frappe.utils.today())

	return journal_entry.name


def enforce_positive_values(doc: "CustomBankTransaction"):
	"""Convert any negative values to positive values.

	Bank Statements often contain negative values (mostly for withdrawals and
	fees) while ERPNext expects positive values only. To avoid errors during
	Data Import, we accept negative values but convert them to positive values.
	"""
	for fieldname in ["deposit", "withdrawal", "included_fee", "excluded_fee"]:
		doc.convert_to_positive_value(fieldname)

	# Re-call this function as the original function runs before this one and values are not converted
	doc.handle_excluded_fee()
