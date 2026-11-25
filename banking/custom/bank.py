import frappe
from frappe import _
from frappe.utils import get_link_to_form

from banking.ebics.utils import get_protocol_versions as _get_protocol_versions


def validate(doc, method):
	validate_ebics_host_id_change(doc)


def on_update(doc, method):
	move_ebics_registrations(doc)

	if doc.has_value_changed("ebics_host_id"):
		# The old host received INI, so the new host needs INI as well.
		frappe.db.set_value("EBICS User", {"bank": doc.name}, "ini_sent", 0)


def validate_ebics_host_id_change(doc):
	"""Allow a new host ID until the bank knows the keys of an EBICS User."""
	if not doc.has_value_changed("ebics_host_id"):
		return

	ebics_user = frappe.db.exists("EBICS User", {"bank": doc.name, "initialized": 1})
	if ebics_user:
		frappe.throw(
			_(
				"You cannot change the EBICS Host ID of bank {0}, because EBICS User {1} is initialized."
			).format(frappe.bold(doc.name), get_link_to_form("EBICS User", ebics_user))
		)

	ebics_user = frappe.db.exists("EBICS User", {"bank": doc.name})
	if ebics_user and not doc.ebics_host_id:
		frappe.throw(
			_("You cannot remove the EBICS Host ID of bank {0}, because EBICS User {1} uses it.").format(
				frappe.bold(doc.name), get_link_to_form("EBICS User", ebics_user)
			)
		)


def move_ebics_registrations(doc):
	"""The license backend registers each EBICS User with the host ID. Register them under the new one."""
	previous = doc.get_doc_before_save()
	if not previous or previous.ebics_host_id == doc.ebics_host_id:
		return

	old_host_id = previous.ebics_host_id
	moved_users = []
	try:
		for name in frappe.get_all("EBICS User", filters={"bank": doc.name}, pluck="name"):
			ebics_user = frappe.get_doc("EBICS User", name)
			ebics_user.move_registration(old_host_id, doc.ebics_host_id)
			moved_users.append(ebics_user)
	except Exception:
		# The save rolls back and keeps the old host ID, so register the moved users under it again.
		for ebics_user in moved_users:
			ebics_user.move_registration(doc.ebics_host_id, old_host_id)
		raise


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
