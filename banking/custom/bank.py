import frappe
from frappe import _
from frappe.utils import get_link_to_form

from banking.ebics.utils import get_protocol_versions as _get_protocol_versions


def validate(doc, method):
	validate_ebics_host_id_change(doc)


def validate_ebics_host_id_change(doc):
	"""The license backend registers each EBICS User with the host ID. It must not change while in use."""
	if not doc.has_value_changed("ebics_host_id"):
		return

	ebics_user = frappe.db.exists("EBICS User", {"bank": doc.name})
	if ebics_user:
		frappe.throw(
			_("You cannot change the EBICS Host ID of bank {0}, because EBICS User {1} uses it.").format(
				frappe.bold(doc.name), get_link_to_form("EBICS User", ebics_user)
			)
		)


@frappe.whitelist()
def get_protocol_versions(bank_name: str):
	bank = frappe.get_doc("Bank", bank_name)
	bank.check_permission("write")

	if not bank.ebics_host_id or not bank.ebics_url:
		frappe.throw(
			_("Bank {0} does not have EBICS Host ID or URL set").format(bank_name),
			title=_("EBICS Configuration Missing"),
		)

	return _get_protocol_versions(bank.ebics_host_id, bank.ebics_url)
