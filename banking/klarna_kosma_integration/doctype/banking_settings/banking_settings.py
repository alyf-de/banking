# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt
import json
from requests import HTTPError
from semantic_version import Version
from typing import Dict, Optional, Union

import frappe
from frappe import _
from frappe.model.document import Document

from banking.klarna_kosma_integration.admin import Admin
from banking.klarna_kosma_integration.exception_handler import BankingError
from banking.klarna_kosma_integration.utils import (
	create_bank_account,
	needs_consent,
	update_bank_account,
	update_bank,
)


class BankingSettings(Document):
	def before_validate(self):
		self.update_fintech_license()

	def update_fintech_license(self):
		if not self.enabled:
			return self.reset_fintech_license()

		try:
			response = Admin(self).request.get_fintech_license()
			response.raise_for_status()
		except HTTPError:
			return self.reset_fintech_license()
		except Exception:
			return

		data = response.json().get("message", {})
		self.fintech_licensee_name = data.get("licensee_name")
		self.fintech_license_key = data.get("license_key")

	def reset_fintech_license(self):
		self.fintech_licensee_name = None
		self.fintech_license_key = None


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
def add_bank_account(
	account_data: Union[str, dict], gl_account: str, company: str, bank_name: str
) -> None:
	if isinstance(account_data, str):
		account_data = json.loads(account_data)

	update_bank(account_data, bank_name)

	existing_bank_account = frappe.db.exists("Bank Account", {"account": gl_account})
	if existing_bank_account:
		update_bank_account(account_data, existing_bank_account, relink=True)
	else:
		create_bank_account(account_data, bank_name, company, gl_account)


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
		now=frappe.conf.developer_mode,
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
	banking_settings = frappe.get_single("Banking Settings")
	if not banking_settings.enabled:
		return

	if banking_settings.enable_klarna_kosma:
		daily_sync_kosma()

	if banking_settings.enable_ebics:
		daily_sync_ebics()


def daily_sync_kosma():
	accounts_list = []

	for bank, company in frappe.get_all(
		"Bank Consent", fields=["bank", "company"], as_list=True
	):
		accounts = get_bank_accounts_to_sync(bank, company)
		for account in accounts:
			bank_account = frappe.db.exists("Bank Account", {"iban": account.get("iban")})
			if not bank_account:
				continue

			update_bank_account(account, bank_account)
			accounts_list.append(bank_account)

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


def daily_sync_ebics():
	from banking.ebics.utils import sync_ebics_transactions

	for ebics_user in frappe.get_all(
		"EBICS User",
		filters={
			"initialized": 1,
			"bank_keys_activated": 1,
			"passphrase": ("is", "set"),
			"keyring": ("is", "set"),
		},
		pluck="name",
	):
		frappe.enqueue(
			sync_ebics_transactions,
			ebics_user=ebics_user,
		)


def intraday_sync_ebics():
	from banking.ebics.utils import sync_ebics_transactions

	banking_settings = frappe.get_single("Banking Settings")
	if not banking_settings.enabled or not banking_settings.enable_ebics:
		return

	for ebics_user in frappe.get_all(
		"EBICS User",
		filters={
			"initialized": 1,
			"bank_keys_activated": 1,
			"passphrase": ("is", "set"),
			"keyring": ("is", "set"),
			"intraday_sync": 1,
		},
		pluck="name",
	):
		frappe.enqueue(
			sync_ebics_transactions,
			ebics_user=ebics_user,
			intraday=True,
		)


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
