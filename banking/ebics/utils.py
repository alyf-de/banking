from frappe import frappe
from banking.ebics.manager import EBICSManager


def get_ebics_manager(ebics_user: str) -> "EBICSManager":
	"""Get an EBICSManager instance for the given EBICS User.

	:param ebics_user: The name of the EBICS User record.
	"""
	banking_settings = frappe.get_single("Banking Settings")
	banking_settings.ensure_ebics_keyring_passphrase()

	manager = EBICSManager(
		license_name=banking_settings.fintech_licensee_name,
		license_key=banking_settings.get_password("fintech_license_key"),
	)

	manager.set_keyring(
		frappe.get_site_path("private", "files", "ebics_keyring"),
		banking_settings.get_password("ebics_keyring_passphrase"),
	)

	bank, partner_id, user_id = frappe.db.get_value(
		"EBICS User", ebics_user, ["bank", "partner_id", "user_id"]
	)
	host_id, url = frappe.db.get_value("Bank", bank, ["ebics_host_id", "ebics_url"])

	manager.set_user(partner_id, user_id)
	manager.set_bank(host_id, url)

	return manager
