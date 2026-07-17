import frappe
from frappe import _
from frappe.utils import flt


def reconcile_created_from_bank_transaction(doc, method=None):
	"""Reconcile a voucher submitted from Edit-in-Full-Page with its reserved Bank Transaction."""
	if not doc.get("created_from_bank_transaction"):
		return

	bank_transaction = frappe.get_doc("Bank Transaction", doc.created_from_bank_transaction, for_update=True)

	if bank_transaction.reserved_voucher_type != doc.doctype or bank_transaction.reserved_voucher != doc.name:
		frappe.throw(
			_("Bank Transaction {0} is not reserved for {1} {2}.").format(
				frappe.bold(bank_transaction.name), _(doc.doctype), frappe.bold(doc.name)
			)
		)

	amount = get_voucher_bank_amount(doc, bank_transaction)

	vouchers = [
		{
			"payment_doctype": doc.doctype,
			"payment_name": doc.name,
			"amount": amount,
		}
	]

	if bank_transaction.unallocated_amount <= 0.0:
		frappe.throw(_("Bank Transaction {0} is already fully reconciled").format(bank_transaction.name))

	bank_transaction.assert_reservation_allows(vouchers)
	bank_transaction.reconcile_paid_vouchers(vouchers)
	bank_transaction.reserved_voucher_type = None
	bank_transaction.reserved_voucher = None
	bank_transaction.save()


def release_bank_transaction_reservation(doc, method=None):
	"""Clear the Bank Transaction reservation when the draft voucher is deleted."""
	if not doc.get("created_from_bank_transaction"):
		return

	if not frappe.db.exists("Bank Transaction", doc.created_from_bank_transaction):
		return

	bank_transaction = frappe.get_doc("Bank Transaction", doc.created_from_bank_transaction, for_update=True)

	if (
		bank_transaction.reserved_voucher_type == doc.doctype
		and bank_transaction.reserved_voucher == doc.name
	):
		bank_transaction.db_set(
			{
				"reserved_voucher_type": None,
				"reserved_voucher": None,
			},
			update_modified=False,
		)


def get_voucher_bank_amount(doc, bank_transaction) -> float:
	"""Validate the voucher affects the expected bank GL account and return its bank-side amount."""
	bank_gl_account = frappe.get_value("Bank Account", bank_transaction.bank_account, "account")
	is_deposit = flt(bank_transaction.deposit) > 0

	if doc.doctype == "Journal Entry":
		amount = _get_journal_entry_bank_amount(doc, bank_gl_account, is_deposit)
	elif doc.doctype == "Payment Entry":
		amount = _get_payment_entry_bank_amount(doc, bank_gl_account, is_deposit)
	else:
		frappe.throw(_("Unsupported voucher type {0}.").format(doc.doctype))

	if amount <= 0:
		frappe.throw(
			_(
				"The voucher does not affect bank account {0} in the expected direction, or the amount is zero."
			).format(frappe.bold(bank_gl_account))
		)

	if amount > flt(bank_transaction.unallocated_amount):
		frappe.throw(
			_("Voucher amount {0} exceeds the unallocated amount {1} of Bank Transaction {2}.").format(
				frappe.bold(amount),
				frappe.bold(bank_transaction.unallocated_amount),
				frappe.bold(bank_transaction.name),
			)
		)

	return amount


def _get_journal_entry_bank_amount(doc, bank_gl_account: str, is_deposit: bool) -> float:
	debit = credit = 0.0
	for row in doc.accounts:
		if row.account != bank_gl_account:
			continue
		debit += flt(row.debit_in_account_currency)
		credit += flt(row.credit_in_account_currency)

	if is_deposit:
		return debit - credit
	return credit - debit


def _get_payment_entry_bank_amount(doc, bank_gl_account: str, is_deposit: bool) -> float:
	if doc.payment_type == "Receive":
		if not is_deposit:
			frappe.throw(
				_("Payment Entry of type {0} cannot reconcile a withdrawal Bank Transaction.").format(
					frappe.bold(_("Receive"))
				)
			)
		if doc.paid_to != bank_gl_account:
			frappe.throw(
				_("Payment Entry bank account {0} does not match Bank Transaction account {1}.").format(
					frappe.bold(doc.paid_to), frappe.bold(bank_gl_account)
				)
			)
		return flt(doc.received_amount)

	if doc.payment_type == "Pay":
		if is_deposit:
			frappe.throw(
				_("Payment Entry of type {0} cannot reconcile a deposit Bank Transaction.").format(
					frappe.bold(_("Pay"))
				)
			)
		if doc.paid_from != bank_gl_account:
			frappe.throw(
				_("Payment Entry bank account {0} does not match Bank Transaction account {1}.").format(
					frappe.bold(doc.paid_from), frappe.bold(bank_gl_account)
				)
			)
		return flt(doc.paid_amount)

	frappe.throw(_("Unsupported Payment Entry type {0}.").format(doc.payment_type))
