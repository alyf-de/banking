# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from semantic_version import Version
from typing import Dict, Optional, Union

import frappe
from erpnext.accounts.doctype.journal_entry.journal_entry import (
	get_default_bank_cash_account,
)
from frappe import _
from frappe.model.document import Document

from banking.klarna_kosma_integration.admin import Admin
from banking.klarna_kosma_integration.exception_handler import BankingError
from banking.klarna_kosma_integration.utils import (
	create_bank_account,
	get_account_name,
	needs_consent,
	update_account,
	update_bank,
)


class BankingSettings(Document):
	pass


@frappe.whitelist()
def get_client_token(
	current_flow: str,
	account: Optional[str] = None,
	from_date: Optional[str] = None,
	to_date: Optional[str] = None,
	company: Optional[str] = None,
) -> Dict:
	"""
	Returns Client Token to render XS2A App & Short Session ID to track session
	"""
	return Admin().get_client_token(current_flow, account, from_date, to_date, company)


@frappe.whitelist()
def fetch_accounts_and_bank(session_id_short: str = None, company: str = None) -> Dict:
	"""
	Fetch Accounts via Flow API after XS2A App interaction.
	"""
	return Admin().flow_accounts(session_id_short, company)


@frappe.whitelist()
def add_bank_accounts(accounts: Union[str, list], company: str, bank_name: str) -> None:
	if isinstance(accounts, str):
		accounts = json.loads(accounts)

	default_gl_account = get_default_bank_cash_account(company, "Bank")
	if not default_gl_account:
		frappe.throw(_("Please setup a default bank account for company {0}").format(company))

	for account in accounts:
		update_bank(account, bank_name)

		if not frappe.db.exists("Bank Account Type", account.get("account_type")):
			frappe.get_doc(
				{
					"doctype": "Bank Account Type",
					"account_type": account.get("account_type"),
				}
			).insert()

		create_bank_account(account, bank_name, company, default_gl_account)


@frappe.whitelist()
def sync_transactions(account: str, session_id_short: Optional[str] = None) -> None:
	"""
	Enqueue transactions sync via the Consent API.
	"""
	bank, company = frappe.db.get_value("Bank Account", account, ["bank", "company"])

	if not session_id_short and needs_consent(bank, company):  # UX
		frappe.throw(
			msg=_(
				"The Consent Token has expired/is unavailable for Bank {0}. Please click on the {1} button"
			).format(frappe.bold(bank), frappe.bold(_("Sync Bank and Accounts"))),
			title=_("Kosma Error"),
		)

	frappe.enqueue(
		"banking.klarna_kosma_integration.admin.sync_kosma_transactions",
		account=account,
		session_id_short=session_id_short,
	)

	frappe.msgprint(
		_(
			"Background Transaction Sync is in progress. Please check the Bank Transaction List for updates."
		),
		alert=True,
		indicator="green",
	)


@frappe.whitelist()
def sync_all_accounts_and_transactions():
	"""
	Refresh all Bank accounts and enqueue their transactions sync, via the Consent API.
	Called via hooks.
	"""
	if not frappe.db.get_single_value("Banking Settings", "enabled"):
		return

	accounts_list = []

	for bank, company in frappe.get_all(
		"Bank Consent", fields=["bank", "company"], as_list=True
	):
		accounts = get_bank_accounts_to_sync(bank, company)
		for account in accounts:
			account_name = get_account_name(account)
			bank_account_name = "{} - {}".format(account_name, bank)

			if not frappe.db.exists("Bank Account", bank_account_name):
				continue

			update_account(account, bank_account_name)
			accounts_list.append(bank_account_name)

		if not accounts:
			accounts_list.extend(
				frappe.get_all(
					"Bank Account",
					filters={
						"bank": bank,
						"company": company,
						"kosma_account_id": ["is", "set"],
					},
					pluck="name",
				)
			)

	for bank_account in accounts_list:
		sync_transactions(account=bank_account)


def get_bank_accounts_to_sync(bank: str, company: str) -> list:
	"""
	Get bank accounts from Kosma via the consent API.
	"""
	try:
		return Admin().consent_accounts(bank, company)
	except BankingError:
		return []


@frappe.whitelist()
def fetch_subscription_data() -> Dict:
	"""
	Fetch Accounts via Flow API after XS2A App interaction.
	"""
	return Admin().fetch_subscription()


@frappe.whitelist()
def get_customer_portal_url() -> str:
	"""
	Returns the customer portal URL.
	"""
	return Admin().get_customer_portal_url()


@frappe.whitelist()
def get_app_health() -> Dict:
	"""
	Returns the app health.
	"""
	from frappe.utils.scheduler import is_scheduler_inactive

	messages = {}
	current_app_version = frappe.get_attr("banking.__version__")

	latest_release = get_latest_release_for_branch("alyf-de", "banking")
	if not latest_release:
		return None

	if Version(current_app_version) < Version(latest_release):
		messages["info"] = _(
			"A new version of the Banking app is available ({0}). Please update your instance."
		).format(str(latest_release))

	if is_scheduler_inactive():
		messages["warning"] = _(
			"The scheduler is inactive. Please activate it to continue auto-syncing bank transactions."
		)

	return messages or None


def get_latest_release_for_branch(owner: str, repo: str):
	"""
	Returns the latest release for the current branch.
	"""
	import requests
	from frappe.utils.change_log import get_app_branch

	branch = get_app_branch("banking")
	try:
		releases = requests.get(
			f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=10"
		)
		releases.raise_for_status()

		for release in releases.json():
			if release.get("target_commitish") == branch:
				return release.get("name")[1:]  # remove v prefix
	except Exception:
		frappe.log_error(title=_("Banking Error"), message=_("Error while fetching releases"))
		return None
