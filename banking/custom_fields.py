from banking.ebics.doctype.sepa_payment_order.sepa_payment_order import PaymentOrderStatus
from banking.utils import identity as _


def get_custom_fields():
	return {
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
		],
		"Bank Account": [
			dict(
				fieldname="bank_fee_account",
				fieldtype="Link",
				label="Bank Fee Account",
				options="Account",
				depends_on="is_company_account",
				insert_after="account_subtype",
			),
		],
	}
