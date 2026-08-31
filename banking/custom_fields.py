import frappe

from banking.ebics.doctype.sepa_payment_order.sepa_payment_order import PaymentOrderStatus
from banking.utils import identity as _


def get_custom_fields():
	custom_fields = {
		"Bank": [
			dict(
				fieldname="ebics_section",
				label=_("EBICS"),
				fieldtype="Section Break",
				insert_after="plaid_access_token",
			),
			dict(
				fieldname="ebics_host_id",
				label=_("EBICS Host ID"),
				fieldtype="Data",
				insert_after="ebics_section",
				translatable=0,
			),
			dict(
				fieldname="ebics_url",
				label=_("EBICS URL"),
				fieldtype="Data",
				options="URL",
				insert_after="ebics_host_id",
				translatable=0,
			),
		],
		"Purchase Invoice": [
			dict(
				fieldname="banking_section",
				label=_("Banking"),
				fieldtype="Section Break",
				insert_after="payments_tab",
			),
			# NOTE: pay_to_employee is a field provided by erpnext_germany
			dict(
				fieldname="supplier_bank_account",
				label=_("Supplier Bank Account"),
				fieldtype="Link",
				options="Bank Account",
				insert_after="banking_section",
				depends_on="eval:!doc.pay_to_employee",
			),
			dict(
				fieldname="create_supplier_bank_account",
				label=_("Create Supplier Bank Account"),
				fieldtype="Button",
				insert_after="supplier_bank_account",
				depends_on="eval:doc.docstatus === 0 && doc.supplier_name && !doc.supplier_bank_account && !doc.pay_to_employee && frappe.model.can_create('Bank Account')",
			),
			dict(
				fieldname="employee_bank_account",
				label=_("Employee Bank Account"),
				fieldtype="Link",
				options="Bank Account",
				insert_after="supplier_bank_account",
				depends_on="eval:doc.pay_to_employee",
			),
			dict(
				fieldname="create_employee_bank_account",
				label=_("Create Employee Bank Account"),
				fieldtype="Button",
				insert_after="employee_bank_account",
				depends_on="eval:doc.docstatus === 0 && doc.business_trip_employee && !doc.employee_bank_account && doc.pay_to_employee && frappe.model.can_create('Bank Account')",
			),
		],
		"Payment Schedule": [
			dict(
				fieldname="sepa_payment_order_status",
				label=_("SEPA Payment Order Status"),
				fieldtype="Select",
				options="\n".join(PaymentOrderStatus),
				insert_after="due_date",
				depends_on="eval:doc.parenttype === 'Purchase Invoice'",
				no_copy=1,
				read_only=1,
				allow_on_submit=1,
			),
		],
		"Bank Transaction": [
			dict(
				fieldname="subtransaction_id",
				label=_("Subtransaction ID"),
				fieldtype="Data",
				insert_after="transaction_id",
			),
			dict(
				fieldname="reserved_voucher_type",
				label=_("Reserved Voucher Type"),
				fieldtype="Link",
				options="DocType",
				insert_after="subtransaction_id",
				read_only=1,
				allow_on_submit=1,
				no_copy=1,
			),
			dict(
				fieldname="reserved_voucher",
				label=_("Reserved Voucher"),
				fieldtype="Dynamic Link",
				options="reserved_voucher_type",
				insert_after="reserved_voucher_type",
				read_only=1,
				allow_on_submit=1,
				no_copy=1,
			),
			dict(
				fieldname="on_hold_until",
				label=_("On Hold Until"),
				fieldtype="Date",
				insert_after="reserved_voucher",
				allow_on_submit=1,
				no_copy=1,
			),
		],
		"Journal Entry": [
			dict(
				fieldname="created_from_bank_transaction",
				label=_("Created From Bank Transaction"),
				fieldtype="Link",
				options="Bank Transaction",
				insert_after="cheque_no",
				read_only=1,
				no_copy=1,
			),
		],
		"Payment Entry": [
			dict(
				fieldname="created_from_bank_transaction",
				label=_("Created From Bank Transaction"),
				fieldtype="Link",
				options="Bank Transaction",
				insert_after="reference_no",
				read_only=1,
				no_copy=1,
			),
		],
		"Bank Account": [
			dict(
				fieldname="bank_fee_account",
				fieldtype="Link",
				label=_("Bank Fee Account"),
				options="Account",
				depends_on="eval:doc.is_company_account && doc.account",
				insert_after="account_subtype",
			),
		],
	}

	if "hrms" in frappe.get_installed_apps():
		custom_fields["Expense Claim"] = [
			dict(
				fieldname="sepa_payment_order_status",
				label=_("SEPA Payment Order Status"),
				fieldtype="Select",
				options="\n".join(PaymentOrderStatus),
				insert_after="payable_account",
				no_copy=1,
				read_only=1,
				allow_on_submit=1,
			),
		]

	return custom_fields
