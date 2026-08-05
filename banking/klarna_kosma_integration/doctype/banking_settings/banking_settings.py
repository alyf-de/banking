# Copyright (c) 2022, ALYF GmbH and contributors
# For license information, please see license.txt

import json
from datetime import date, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.data import now_datetime
from requests import HTTPError
from semantic_version import Version

from banking.klarna_kosma_integration.admin import Admin
from banking.overrides.bank_account import get_company_bank_accounts_without_fee_account


class BankingSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from banking.klarna_kosma_integration.doctype.banking_reference_mapping.banking_reference_mapping import (
			BankingReferenceMapping,
		)
		from banking.klarna_kosma_integration.doctype.voucher_matching_default.voucher_matching_default import (
			VoucherMatchingDefault,
		)

		admin_endpoint: DF.Data | None
		api_token: DF.Password | None
		customer_id: DF.Data | None
		enable_automatic_journal_entries_for_bank_fees: DF.Check
		enable_ebics: DF.Check
		enabled: DF.Check
		fintech_license_key: DF.Password | None
		fintech_licensee_name: DF.Data | None
		reference_fields: DF.Table[BankingReferenceMapping]
		voucher_matching_defaults: DF.TableMultiSelect[VoucherMatchingDefault]

	# end: auto-generated types
	def validate(self):
		self.validate_automatic_fee_entry_configuration()

	def before_validate(self):
		self.update_fintech_license()

	def validate_automatic_fee_entry_configuration(self):
		if not self.enable_automatic_journal_entries_for_bank_fees:
			return

		if not self.has_value_changed("enable_automatic_journal_entries_for_bank_fees"):
			return

		missing_fee_accounts = get_company_bank_accounts_without_fee_account()
		if missing_fee_accounts:
			frappe.throw(
				_(
					"Automatic journal entries for bank fees can only be enabled when all company Bank Accounts have a Bank Fee Account."
				)
			)

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


@frappe.whitelist(methods=["POST"])
def sync_all_accounts_and_transactions():
	"""
	Refresh all Bank accounts and enqueue their transactions sync.
	Called via hooks.
	"""
	banking_settings = frappe.get_single("Banking Settings")
	if not banking_settings.enabled:
		return

	if banking_settings.enable_ebics and not frappe.conf.get("disable_ebics", False):
		daily_sync_ebics()


def daily_sync_ebics():
	from banking.ebics.utils import sync_ebics_transactions

	if frappe.conf.developer_mode:
		frappe.throw(
			_("Developer mode is enabled. Please disable it to continue auto-syncing bank transactions.")
		)

	yesterday = (now_datetime() - timedelta(days=1)).date()
	for ebics_user, country in frappe.get_all(
		"EBICS User",
		filters={
			"initialized": 1,
			"bank_keys_activated": 1,
			"passphrase": ("is", "set"),
			"keyring": ("is", "set"),
		},
		fields=["name", "country"],
		as_list=True,
	):
		if successful_request_exists(
			ebics_user, order_type="Z53" if country == "Switzerland" else "C53", request_date=yesterday
		):
			continue

		frappe.enqueue(
			sync_ebics_transactions,
			requested_by="System",
			start_date=yesterday.isoformat(),
			end_date=yesterday.isoformat(),
			ebics_user=ebics_user,
		)


def successful_request_exists(ebics_user: str | None, order_type: str, request_date: date) -> bool:
	existing_requests = frappe.get_all(
		"EBICS Request",
		filters={
			"ebics_user": ebics_user,
			"order_type": order_type,
			"status": "Successful",
		},
		fields=["parameters"],
	)

	for existing_request in existing_requests:
		try:
			params = json.loads(existing_request.parameters)
			start_date = params.get("start_date")
			end_date = params.get("end_date")
			if (
				start_date
				and end_date
				and date.fromisoformat(start_date) <= request_date <= date.fromisoformat(end_date)
			):
				return True
		except json.JSONDecodeError, TypeError, ValueError:
			pass  # If we can't parse, let the sync attempt

	return False


def intraday_sync_ebics():
	from banking.ebics.utils import sync_ebics_transactions

	if frappe.conf.developer_mode:
		frappe.throw(
			_("Developer mode is enabled. Please disable it to continue auto-syncing bank transactions.")
		)

	banking_settings = frappe.get_single("Banking Settings")
	if (not banking_settings.enabled or not banking_settings.enable_ebics) or frappe.conf.get(
		"disable_ebics", False
	):
		return

	today = now_datetime().date().isoformat()
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
			requested_by="System",
			start_date=today,
			end_date=today,
			ebics_user=ebics_user,
			intraday=True,
		)


@frappe.whitelist()
def fetch_subscription_data() -> dict:
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
def get_app_health() -> dict:
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
		releases = requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=10")
		releases.raise_for_status()

		for release in releases.json():
			if release.get("target_commitish") == branch:
				return release.get("name")[1:]  # remove v prefix
	except Exception:
		frappe.log_error(title=_("Banking Error"), message=_("Error while fetching releases"))
		return None


@frappe.whitelist()
def get_doctypes_for_bank_reconciliation() -> dict[str, bool]:
	"""Get Bank Reconciliation doctypes from all the apps and check if they are in the default doctypes"""
	frappe.has_permission("Bank Reconciliation Tool Beta", throw=True)

	all_doctypes = frappe.get_hooks("bank_reconciliation_doctypes")
	settings: BankingSettings = frappe.get_single("Banking Settings")
	default_doctypes = [row.document_type for row in settings.voucher_matching_defaults]
	return {dt: dt in default_doctypes for dt in all_doctypes}
