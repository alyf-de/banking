# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from typing import TYPE_CHECKING, Dict, List, Optional
from banking.klarna_kosma_integration.exception_handler import ExceptionHandler

import frappe
import requests
from frappe import _
from frappe.utils import (
	add_days,
	add_to_date,
	formatdate,
	get_datetime,
	get_first_day,
	getdate,
	nowdate,
)

if TYPE_CHECKING:
	from frappe.model.document import Document


def needs_consent(bank: str, company: str) -> bool:
	"""Returns False if there is atleast 1 hour before consent expires."""
	consent_expiry = frappe.db.get_value(
		"Bank Consent", {"bank": bank, "company": company}, "consent_expiry"
	)
	if not consent_expiry:
		return True

	now = get_datetime()
	expiry_with_buffer = add_to_date(get_datetime(consent_expiry), hours=-1)
	return now > expiry_with_buffer


def get_session_flow_ids(session_id_short: str):
	"""Get stored Session & Flow IDs."""
	doc = frappe.get_doc("Klarna Kosma Session", session_id_short)
	return doc.get_password("session_id"), doc.get_password("flow_id")


def get_consent_data(bank_name: str, company: str):
	"""Get stored bank consent."""
	if needs_consent(bank_name, company):
		frappe.throw(
			_("The Consent Token has expired/is unavailable for Bank {0}.").format(
				frappe.bold(bank_name)
			)
		)

	bank_consent = frappe.get_doc("Bank Consent", {"bank": bank_name, "company": company})
	return bank_consent.consent_id, bank_consent.get_password("consent_token")


def exchange_consent_token(response: Dict, bank: str, company: str) -> str:
	if (not response) or (not isinstance(response, dict)):
		return

	new_consent_token = response.get("consent_token")

	if new_consent_token:
		bank_consent = frappe.get_doc("Bank Consent", {"bank": bank, "company": company})
		bank_consent.consent_token = new_consent_token
		bank_consent.save()
		frappe.db.commit()

	return new_consent_token


def create_session_doc(session_data: Dict, flow_data: Dict) -> "Document":
	if not (session_data and flow_data):
		return

	session_doc = frappe.get_doc(
		{
			"doctype": "Klarna Kosma Session",
			"session_id_short": session_data.get("session_id_short"),
			"session_id": session_data.get("session_id"),
			"consent_scope": json.dumps(session_data.get("consent_scope")),
			"status": "Running",
			"flow_id": flow_data.get("flow_id"),
			"flow_state": flow_data.get("state"),
		}
	)
	return session_doc.insert()


def add_bank(bank_data: Dict) -> str:
	"""
	Create Bank record if absent else update Bank record
	"""
	bank_name = bank_data.get("bank_name")
	if not bank_name:
		frappe.log_error(title=_("Bank Name missing"), message=json.dumps(bank_data))
		frappe.throw(_("Failed to get Bank Name linked to account"))

	if not frappe.db.exists("Bank", bank_name):
		try:
			frappe.get_doc(
				{
					"doctype": "Bank",
					"bank_name": bank_name,
					"swift_number": bank_data.get("bic"),
				}
			).insert()
		except Exception:
			frappe.log_error(title=_("Bank creation failed"), message=frappe.get_traceback())
			frappe.throw(title=_("Kosma Link Error"), msg=_("Bank creation has failed"))
	else:
		update_bank(bank_data, bank_name)

	return bank_name


def update_bank(bank_data: Dict, bank_name: str) -> None:
	"""Update Bank Data"""
	if not frappe.db.exists("Bank", bank_name):
		return

	frappe.db.set_value("Bank", bank_name, "swift_number", bank_data.get("bic"))


def create_bank_account(
	account: Dict, bank_name: str, company: str, default_gl_account: Dict
) -> None:
	account_name = get_account_name(account)
	bank_account_name = "{} - {}".format(account_name, bank_name)

	if not frappe.db.exists("Bank Account", bank_account_name):
		try:
			new_account = frappe.get_doc(
				{
					"doctype": "Bank Account",
					"bank": bank_name,
					"account": default_gl_account.account,
					"account_name": account_name,
					# TODO: add custom field for account holder name ?
					"kosma_account_id": account.get("id"),
					"account_type": account.get("account_type", ""),
					"bank_account_no": account.get("account_number"),
					"iban": account.get("iban"),
					"branch_code": account.get("national_branch_code"),
					"is_company_account": 1,
					"company": company,
				}
			)
			new_account.insert()
		except frappe.UniqueValidationError:
			frappe.msgprint(
				_("Bank account {0} already exists and could not be created again").format(
					new_account.name
				)
			)
		except Exception:
			frappe.log_error(
				title=_("Bank Account creation has failed"),
				message=frappe.get_traceback(),
			)
			frappe.throw(
				_("There was an error creating a Bank Account while linking with Kosma."),
				title=_("Kosma Link Error"),
			)
	else:
		update_account(account, bank_account_name)


def update_account(account_data: str, bank_account_name: str) -> None:
	try:
		account = frappe.get_doc("Bank Account", bank_account_name)
		account.update(
			{
				"account_type": account_data.get("account_type", ""),
				"kosma_account_id": account_data.get("id"),
			}
		)
		account.save()
	except Exception:
		frappe.log_error(
			title=_("Kosma Error - Bank Account Update"), message=frappe.get_traceback()
		)
		frappe.throw(
			_("There was an error updating Bank Account {} while linking with Kosma.").format(
				bank_account_name
			),
			title=_("Kosma Link Error"),
		)


def get_account_name(account: Dict) -> str:
	"""
	Generates and returns distinguishable account name.

	Here we can consider alias + holder name to make a distinct account name
	E.g. of Aliases:
	- Accounts: [{alias: "Girokonto"}, {alias: "Girokonto"}, {alias: "Girokonto"}]
	- Accounts: [{alias: "My checking account"}, {alias: "My salary account"}, {alias: "My restricted account"}]
	- (distinct) Accounts: [{alias: "Girokonto (Max Mustermann)"}, {alias: "Girokonto (Hans Mustermann)"}]
	"""
	alias = account.get("alias")
	if alias:
		is_alias_distinct = "(" in alias
		alias_with_acc_holder = f"{alias} ({account.get('holder_name', '')})"

		account_name = alias if is_alias_distinct else alias_with_acc_holder
	else:
		account_name = account.get("iban") or account.get("account_number")

	return account_name


def create_bank_transactions(
	account: str, transactions: List[Dict], via_flow_api: bool = False
) -> None:
	last_sync_date = None
	try:
		for transaction in reversed(transactions):
			transaction_created = new_bank_transaction(account, transaction)

			if not transaction_created or via_flow_api:
				# Don't set last integration date if via Flow API (one time action with arbitrary time period)
				# or if transaction was not inserted
				continue

			last_sync_date = transaction.get("value_date") or transaction.get("date")

	except Exception:
		frappe.log_error(title=_("Kosma Transaction Error"), message=frappe.get_traceback())
		frappe.throw(_("Error creating transactions"))
	finally:
		if last_sync_date:
			frappe.db.set_value("Bank Account", account, "last_integration_date", last_sync_date)


def new_bank_transaction(account: str, transaction: Dict) -> bool:
	amount_data = transaction.get("amount", {})
	amount = (
		amount_data.get("amount", 0) / 100
	)  # https://docs.openbanking.klarna.com/xs2a/objects/amount.html

	is_credit = transaction.get("type") == "CREDIT"
	debit = 0 if is_credit else float(amount)
	credit = float(amount) if is_credit else 0

	state_map = {
		"PROCESSED": "Settled",
		"PENDING": "Pending",
		"CANCELED": "Settled",  # TODO: is this status ok ? Should we even consider making cancelled/failed records
		"FAILED": "Settled",
	}
	status = state_map[transaction.get("state")]
	transaction_id = transaction.get("transaction_id")

	if not transaction_id and transaction.get("state") == "PENDING":
		# Dont insert pending transactions. transaction_id is absent only for Pending state
		# Ref: https://docs.openbanking.klarna.com/xs2a/objects/transaction.html
		return False

	if frappe.db.exists("Bank Transaction", {"transaction_id": transaction_id}):
		return False

	new_transaction = frappe.get_doc(
		{
			"doctype": "Bank Transaction",
			"date": getdate(transaction.get("value_date") or transaction.get("date")),
			"status": status,
			"bank_account": account,
			"deposit": credit,
			"withdrawal": debit,
			"currency": amount_data.get("currency"),
			"transaction_id": transaction_id,
			"reference_number": transaction.get("bank_references", {}).get("end_to_end"),
			"description": transaction.get("reference"),
			"bank_party_name": transaction.get("counter_party", {}).get("holder_name"),
			"bank_party_iban": transaction.get("counter_party", {}).get("iban"),
			"bank_party_account_number": transaction.get("counter_party", {}).get(
				"account_number"
			),
		}
	)
	new_transaction.insert()
	new_transaction.submit()
	return True


def get_from_to_date(from_date: Optional[str] = None, to_date: Optional[str] = None):
	"""
	Get from and to date for session and consent creation.
	Default to start of the month and 90 days from now.
	"""
	month_start = get_first_day(nowdate())

	from_date = from_date or month_start
	to_date = to_date or add_days(nowdate(), 90)
	return formatdate(from_date, "YYYY-MM-dd"), formatdate(to_date, "YYYY-MM-dd")


def to_json(response: requests.models.Response) -> Dict:
	"""
	Check if response is in JSON format. If not, return {}
	"""
	is_json = "application/json" in response.headers.get("Content-Type", "")
	return response.json() if is_json else {}


def account_last_sync_date(account_name: str):
	"""Get Account's Last Integration Date or Consent Start Date."""
	last_sync_date, bank, company = frappe.db.get_value(
		"Bank Account", account_name, ["last_integration_date", "bank", "company"]
	)
	if last_sync_date:
		return formatdate(last_sync_date, "YYYY-MM-dd")
	else:
		date = frappe.db.get_value(
			"Bank Consent", {"bank": bank, "company": company}, "consent_start"
		)
		return formatdate(date, "YYYY-MM-dd")


def get_consent_start_date(session_id_short: str) -> str:
	"""Get start date for current consent token."""
	consent_scope = frappe.get_value(
		"Klarna Kosma Session", session_id_short, "consent_scope"
	)
	consent_start = (
		json.loads(consent_scope).get("transactions", {}).get("from_date", None)
	)
	return consent_start


def get_current_ip() -> Optional[str]:
	"""Return the current IP or `None`.

	- If run outside of a request context, return `None` (e.g. in a background job).
	- If run on localhost, return the public IP address as queried from AWS checkip.
	"""
	if not frappe.request:
		return None

	ip_address = frappe.local.request_ip
	if ip_address == "127.0.0.1":
		try:
			ip_address = requests.get("https://checkip.amazonaws.com", timeout=3).text.strip()
		except Exception as exc:
			ExceptionHandler(exc)

	return ip_address


def get_account_data_for_request(account: str):
	if not account:
		return {}

	iban, account_id = frappe.db.get_value(
		"Bank Account", account, ["iban", "kosma_account_id"]
	)
	return {"iban": iban, "account_id": account_id}


def set_session_state(session_id_short: str, result: str = None):
	result = result or {}

	frappe.db.set_value(
		"Klarna Kosma Session",
		session_id_short,
		{
			"flow_state": result.get("state", "EXCEPTION"),
			"status": result.get("session_state", "Running"),
		},
	)
