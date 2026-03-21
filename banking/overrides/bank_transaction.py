import frappe
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction
from frappe import _
from frappe.core.utils import find
from frappe.utils import flt, getdate
from frappe.utils.data import get_link_to_form


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

	if flt(doc.withdrawal) and flt(doc.included_fee) > flt(doc.withdrawal):
		frappe.throw(
			_("The field {0} cannot be greater than {1}. Please verify the input data.").format(
				_(doc.meta.get_label("included_fee")), _(doc.meta.get_label("withdrawal"))
			)
		)

	cost_center = frappe.get_cached_value("Company", doc.company, "cost_center")
	account = frappe.get_cached_value("Bank Account", doc.bank_account, "account")
	debit, credit = (doc.deposit, 0) if doc.deposit else (0, doc.withdrawal)

	if flt(frappe.db.get_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees")):
		create_je_bank_fees(doc, cost_center, date, account, debit, credit)


def create_je_bank_fees(doc, cost_center, date, account, debit, credit):
	# Create a journal entry for included bank fees.
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
		# Only adjust withdrawals, because deposits never include the fee in the bank amount.
		credit_no_fee = credit - included_fee
		doc.allocated_amount = included_fee
		doc.unallocated_amount = debit + (credit_no_fee or 0)
		allocated_amount = included_fee
	else:
		allocated_amount = 0

	# For deposits, this entry remains unallocated so deposit reconciliation still works correctly.
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
):
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Bank Entry"
	journal_entry.posting_date = date
	journal_entry.company = company
	journal_entry.user_remark = _("Auto-created from Bank Transaction {0}").format(bank_transaction)
	journal_entry.is_system_generated = 1
	journal_entry.cheque_no = bank_transaction
	journal_entry.cheque_date = date
	journal_entry.multi_currency = 1

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
	frappe.db.set_value("Journal Entry", journal_entry.name, "clearance_date", frappe.utils.today())

	return journal_entry.name
