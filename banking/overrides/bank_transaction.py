import json

import frappe
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction
from frappe import _
from frappe.core.utils import find
from frappe.utils import flt, getdate
from frappe.utils.data import evaluate_filters


class CustomBankTransaction(BankTransaction):
	def before_validate(self):
		"""Normalize imported signs before ERPNext computes fees and balances.

		Order matters here:
		- ERPNext's `BankTransaction.before_validate` applies `handle_excluded_fee()`
		  and then recalculates `unallocated_amount`.
		- Imported statements can contain negative deposit/withdrawal/fee values.
		- If we normalize after the core method, fees may be applied in the wrong
		  direction and `unallocated_amount` can be computed from pre-normalized
		  values (stale until a later validation cycle).

		By normalizing first and calling `super().before_validate()` second, core
		fee handling and amount calculations run once on a consistent, positive-value
		representation in the same validation pass.
		"""
		self.enforce_positive_values()
		super().before_validate()

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

	def convert_to_positive_value(self, fieldname: str):
		cur_value = self.get(fieldname)
		if cur_value is not None and flt(cur_value) < 0:
			self.set(fieldname, abs(flt(cur_value)))

	def enforce_positive_values(self):
		"""Convert any negative values to positive values.

		Bank Statements often contain negative values (mostly for withdrawals and
		fees) while ERPNext expects positive values only. To avoid errors during
		Data Import, we accept negative values but convert them to positive values.
		"""
		for fieldname in ["deposit", "withdrawal", "included_fee", "excluded_fee"]:
			self.convert_to_positive_value(fieldname)


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

	for fieldname in ["deposit", "withdrawal"]:
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

	create_je_automatic_rules(doc, cost_center, date, account, debit, credit)


def on_cancel(doc, method):
	"""Cancel the automatically created Journal Entries for this Bank Transaction."""
	for journal_entry in frappe.get_all(
		"Journal Entry",
		filters=[
			["Journal Entry", "docstatus", "=", 1],
			["Journal Entry", "is_system_generated", "=", 1],
			["Journal Entry Account", "reference_type", "=", "Bank Transaction"],
			["Journal Entry Account", "reference_name", "=", doc.name],
		],
		pluck="name",
		distinct=True,
	):
		frappe.get_doc("Journal Entry", journal_entry).cancel()


def create_je_automatic_rules(doc, cost_center, date, account, debit, credit):
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
		order_by="priority DESC, creation ASC",
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
		doc.allocated_amount = (doc.allocated_amount or 0) + debit + credit
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
	journal_entry.is_system_generated = 1

	journal_entry.append(
		"accounts",
		{
			"account": account,
			"bank_account": bank_account,
			"debit_in_account_currency": debit,
			"credit_in_account_currency": credit,
			"cost_center": cost_center,
			"reference_type": "Bank Transaction",
			"reference_name": bank_transaction,
		},
	)

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
	frappe.db.set_value("Journal Entry", journal_entry.name, "clearance_date", date)

	return journal_entry.name
