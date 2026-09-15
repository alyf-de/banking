---
title: Interaction with other Apps
order: 80
roles:
  - System Manager
---

> **NOTE**: This document mainly applies to v15+. For earlier versions, things may be different.

# [ERPNext](https://github.com/frappe/erpnext)

ERPNext needs to be installed because it provides the **Bank Transaction** DocType.

You can reconcile **Bank Transactions** against **Payment Entry** and **Journal Entry**. These are deemed "paid" vouchers - the **Bank Transaction** is already booked and only needs to be allocated.

You can also reconcile against "unpaid" **Purchase Invoice** and **Sales Invoice**. In this case, the appropriate **Payment Entry** or **Journal Entry** will be created for you and allocated to the **Bank Transaction**.

# [ERPNext Germany](https://github.com/alyf-de/erpnext_germany)

ERPNext Germany provides a DocType called **Business Trip**. A **Purchase Invoice** created from a **Business Trip** references the _Business Trip_ and _Employee_ in order to reimburse invoices advanced by the employee. If this is the case, a **SEPA Payment Order** created from the **Purchase Invoice** will be directed at the _Employee_, not at the _Supplier_.

To enable this feature, the banking app adds a field _Employee Bank Account_ to the **Purchase Invoice** form.

# [Mint](https://github.com/The-Commit-Company/mint)

Mint features a dedicated UI for bank reconciliation. It has some features we're lacking (e.g. an "undo" button) and lacks some features we have (e.g. matching voucher number and bank transaction purpose). All **Bank Transactions** synced via EBICS or imported manually (CAMT, MT940) can just as well be reconciled via mint.

# [HRMS](https://github.com/frappe/hrms)

If HRMS is installed, you can reconcile **Bank Transactions** against unpaid **Expense Claims**.

You can also create a **SEPA Payment Order** directly from an approved **Expense Claim** to reimburse the employee.

# [Lending](https://github.com/frappe/lending)

If Lending is installed, you can – in theory – reconcile **Bank Transactions** against **Loan Repayment** and **Loan Disbursement**. Note that this features is, to our knowledge at the time, unused and untested. Let us know if you need this feature.

# Your app

The banking app makes use of the following hooks:

- `bank_reconciliation_doctypes` (`list[str]`)

    List of DocTypes that should be shown in the bank reconciliation UI.

- `get_matching_queries` (`str`)

    Dotted path to a function with a signature [like this](https://github.com/alyf-de/banking/blob/af6a149d5c3819d17c3abaca5c8c1b1b21d90bbe/banking/klarna_kosma_integration/doctype/bank_reconciliation_tool_beta/bank_reconciliation_tool_beta.py#L562-L575). It is called when the user selects a **Bank Transaction** in the reconciliation tool. It should return a list of `frappe.qb` queries (e.g. one per DocType) for your app's vouchers matching the selected **Bank Transaction**.

- `get_payment_entries` (`str`)

    Dotted path to a function with a signature [like this](https://github.com/alyf-de/banking/blob/af6a149d5c3819d17c3abaca5c8c1b1b21d90bbe/banking/klarna_kosma_integration/doctype/bank_reconciliation_tool_beta/unpaid_vouchers.py#L22). It is called when the user clicks on "reconcile" in the reconciliation tool. It receives a Bank Transaction and a list of selected vouchers. It should return a list where your apps's unpaid vouchers have been replaced with appropriate Journal Entries or Payment Entries. Otherwise, you can just return `None` to leave things unchanged.

- `before_reconcile` (client script handler)

    A client-side handler on **Bank Reconciliation Tool Beta** that runs before reconciliation. Registered via `frappe.ui.form.on`, it receives `(frm, transaction, selected_vouchers)` and can return an object that is merged into the reconcile call's `extra_params`. This is used internally for the cross-currency reconciliation flow but can also be used by other apps to inject custom logic before reconciliation proceeds.
