import frappe
from frappe import _

from banking.ebics.utils import get_protocol_versions as _get_protocol_versions


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
