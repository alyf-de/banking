import json

import frappe
from erpnext.accounts.doctype.bank_transaction.bank_transaction import BankTransaction
from frappe import _
from frappe.core.utils import find
from frappe.utils import flt, getdate
from frappe.utils.data import evaluate_filters, get_link_to_form

from banking.klarna_kosma_integration.doctype.bank_reconciliation_rule.bank_reconciliation_rule import (
	get_party_account_type,
	party_type_matches_account_type,
)


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

		self.assert_reservation_allows(vouchers)

		pe_length_before = len(self.payment_entries)
		self.reconcile_paid_vouchers(vouchers)

		if len(self.payment_entries) != pe_length_before:
			self.save()  # runs on_update_after_submit

	def assert_reservation_allows(self, vouchers: list):
		"""Reject payment entries other than the reserved voucher while a reservation is active."""
		if not self.reserved_voucher:
			return

		for voucher in vouchers:
			voucher_type, voucher_name = voucher["payment_doctype"], voucher["payment_name"]
			if voucher_type == self.reserved_voucher_type and voucher_name == self.reserved_voucher:
				continue

			frappe.throw(
				_(
					"Bank Transaction {0} is reserved by draft {1} {2}. "
					"Submit or delete that voucher before reconciling other entries."
				).format(
					frappe.bold(self.name),
					_(self.reserved_voucher_type),
					frappe.bold(self.reserved_voucher),
				)
			)

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

	def get_rounded(self, fieldname: str) -> float:
		return flt(self.get(fieldname), self.precision(fieldname))


def on_update_after_submit(doc, event):
	"""Validate reservation and over-allocation after submit."""
	_validate_new_payment_entries_against_reservation(doc)

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


def _validate_new_payment_entries_against_reservation(doc):
	if not doc.reserved_voucher:
		return

	before = doc.get_doc_before_save()
	before_keys = {
		(entry.payment_document, entry.payment_entry) for entry in (before.payment_entries if before else [])
	}
	reserved_key = (doc.reserved_voucher_type, doc.reserved_voucher)

	for entry in doc.payment_entries:
		key = (entry.payment_document, entry.payment_entry)
		if key in before_keys or key == reserved_key:
			continue

		frappe.throw(
			_(
				"Bank Transaction {0} is reserved by draft {1} {2}. "
				"Submit or delete that voucher before reconciling other entries."
			).format(
				frappe.bold(doc.name),
				_(doc.reserved_voucher_type),
				frappe.bold(doc.reserved_voucher),
			)
		)


def has_zero_transaction_amount_with_included_fee(doc: "CustomBankTransaction") -> bool:
	return (
		doc.get_rounded("deposit") == 0
		and doc.get_rounded("withdrawal") == 0
		and doc.get_rounded("included_fee") > 0
	)


def log_zero_transaction_amount_with_included_fee(doc: "CustomBankTransaction") -> None:
	frappe.log_error(
		title=_("Unsupported Bank Transaction with included fee"),
		message=_(
			"Bank Transaction {0} has no deposit or withdrawal but has an included fee of {1}. "
			"Automatic bank fee reconciliation was skipped; please review manually."
		).format(doc.name, doc.get_formatted("included_fee")),
		reference_doctype="Bank Transaction",
		reference_name=doc.name,
	)


def before_submit(doc: "CustomBankTransaction", method):
	date = doc.date or frappe.utils.nowdate()

	if not doc.bank_account:
		frappe.throw(
			_("The field {0} is required. Please verify the input data.").format(
				_(doc.meta.get_label("bank_account"))
			)
		)

	if has_zero_transaction_amount_with_included_fee(doc):
		log_zero_transaction_amount_with_included_fee(doc)
		return

	if doc.get_rounded("deposit") == 0 and doc.get_rounded("withdrawal") == 0:
		return

	for fieldname in ["deposit", "withdrawal", "included_fee"]:
		if doc.get_rounded(fieldname) < 0:
			frappe.throw(
				_("The field {0} is negative. Please verify the input data.").format(
					_(doc.meta.get_label(fieldname))
				)
			)

	if doc.get_rounded("withdrawal") and doc.get_rounded("included_fee") > doc.get_rounded("withdrawal"):
		frappe.throw(
			_("The field {0} cannot be greater than {1}. Please verify the input data.").format(
				_(doc.meta.get_label("included_fee")), _(doc.meta.get_label("withdrawal"))
			)
		)

	cost_center = frappe.get_cached_value("Company", doc.company, "cost_center")
	account = frappe.get_cached_value("Bank Account", doc.bank_account, "account")
	debit, credit = (
		(doc.get_rounded("deposit"), 0.0)
		if doc.get_rounded("deposit")
		else (0.0, doc.get_rounded("withdrawal"))
	)

	if flt(frappe.db.get_single_value("Banking Settings", "enable_automatic_journal_entries_for_bank_fees")):
		create_je_bank_fees(doc, cost_center, date, account, debit, credit)

	create_je_automatic_rules(doc, cost_center, date, account, debit, credit)


def create_je_bank_fees(doc, cost_center, date, account, debit, credit):
	# Create a journal entry for included bank fees.
	included_fee = doc.included_fee

	if included_fee is None or included_fee <= 0:
		return

	# Only create fee JEs for withdrawals. Deposit-side fees are deferred
	# to reconciliation, where the correct counter-account is known.
	if not flt(doc.withdrawal):
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
		doc.append(
			"payment_entries",
			{
				"payment_document": "Journal Entry",
				"payment_entry": je_fee_name,
				"allocated_amount": included_fee,
			},
		)
		# Recompute from the rows so existing allocations are preserved if this helper
		# is reused outside the current submit flow.
		doc.allocated_amount = sum(flt(entry.allocated_amount) for entry in doc.payment_entries)
		doc.unallocated_amount = abs(flt(doc.withdrawal) - flt(doc.deposit)) - doc.allocated_amount
	# Deposit fees are linked via the Journal Entry reference only and must stay
	# out of the reconciliation table.

	if doc.unallocated_amount == 0:
		doc.status = "Reconciled"


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


def get_party_error(doc, account_type: str, target_account: str) -> str | None:
	"""Explain why the Bank Transaction cannot supply a party for `target_account`.

	The transaction is the only source for the party of the automatic Journal Entry,
	so a rule pointing at a Receivable or Payable account is not applicable to
	transactions without a fitting party. Returns None if the party fits.
	"""
	if not (doc.party_type and doc.party):
		return _("Bank Transaction {0} has no party, but target account {1} is a {2} account.").format(
			doc.name, target_account, _(account_type)
		)

	if not party_type_matches_account_type(doc.party_type, account_type):
		return _(
			"Bank Transaction {0} has party type {1}, which cannot be booked against the {2} account {3}."
		).format(doc.name, _(doc.party_type), _(account_type), target_account)

	return None


def create_je_automatic_rules(doc, cost_center, date, account, debit, credit):
	allocated_amount = sum(flt(entry.allocated_amount) for entry in doc.payment_entries)
	remaining_amount = abs(flt(doc.withdrawal) - flt(doc.deposit)) - allocated_amount
	if remaining_amount <= 0:
		return

	debit, credit = (remaining_amount, 0.0) if flt(doc.deposit) else (0.0, remaining_amount)

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

		party = {}
		if party_account_type := get_party_account_type(target_account):
			if reason := get_party_error(doc, party_account_type, target_account):
				# Stop instead of raising, which would abort a whole statement import,
				# and instead of falling through to the next rule, which would book the
				# amount to an account the highest-priority match did not intend.
				frappe.log_error(
					title="Bank Reconciliation Rule not applied",
					message=reason,
					reference_doctype="Bank Reconciliation Rule",
					reference_name=br_rule_name,
				)
				return

			party = {"party_type": doc.party_type, "party": doc.party}

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
			**party,
		)
		doc.append(
			"payment_entries",
			{
				"payment_document": "Journal Entry",
				"payment_entry": je_auto_name,
				"allocated_amount": debit + credit,
			},
		)
		doc.allocated_amount = sum(flt(entry.allocated_amount) for entry in doc.payment_entries)
		doc.unallocated_amount = abs(flt(doc.withdrawal) - flt(doc.deposit)) - doc.allocated_amount
		if doc.unallocated_amount == 0:
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
	party_type: str | None = None,
	party: str | None = None,
):
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.voucher_type = "Bank Entry"
	journal_entry.posting_date = date
	journal_entry.company = company
	journal_entry.user_remark = (
		_("Auto-created from Bank Transaction {0} by Bank Reconciliation Rule {1}").format(
			bank_transaction, rule
		)
		if rule
		else _("Auto-created from Bank Transaction {0}").format(bank_transaction)
	)
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
			"party_type": party_type,
			"party": party,
		},
	)

	journal_entry.submit()
	frappe.db.set_value("Journal Entry", journal_entry.name, "clearance_date", date)

	return journal_entry.name
