---
title: ALYF Banking
order: 0
roles:
  - Accounts User
  - Accounts Manager
  - System Manager
---

ALYF Banking imports bank statements into ERPNext as **Bank Transactions** and helps you reconcile them against vouchers.

## Import bank statements

- Sync statements automatically via [EBICS](ebics-integration.md) (Austria, France, Germany, Switzerland)
- Upload [CAMT](camt-file-upload.md) or [MT940](mt940-file-upload.md) files by hand
- Import [Wise](wise-integration.md) balance statements as CAMT files

## Reconcile transactions

Use [Bank Reconciliation Tool Beta](bank-reconciliation-tool-beta.md) to match **Bank Transactions** to paid vouchers (**Payment Entry**, **Journal Entry**) or unpaid vouchers (**Sales Invoice**, **Purchase Invoice**, and others when those apps are installed).

## Outgoing payments

Create [SEPA Payment Orders](sepa-payment-order.md) (pain.001) for supplier and employee payments. You can send them via EBICS when your bank access allows it.

## Other apps

See [Interaction with other Apps](interaction-with-other-apps.md) for how Banking works with ERPNext, HRMS, and related apps.
