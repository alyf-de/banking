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

- Sync statements automatically via [EBICS](/app/docs/en/banking/ebics-integration) (Austria, France, Germany, Switzerland)
- Upload [CAMT](/app/docs/en/banking/camt-file-upload) or [MT940](/app/docs/en/banking/mt940-file-upload) files by hand
- Import [Wise](/app/docs/en/banking/wise-integration) balance statements as CAMT files

## Reconcile transactions

Use [Bank Reconciliation Tool Beta](/app/docs/en/banking/bank-reconciliation-tool-beta) to match **Bank Transactions** to paid vouchers (**Payment Entry**, **Journal Entry**) or unpaid vouchers (**Sales Invoice**, **Purchase Invoice**, and others when those apps are installed).

## Outgoing payments

Create [SEPA Payment Orders](/app/docs/en/banking/sepa-payment-order) (pain.001) for supplier and employee payments. You can send them via EBICS when your bank access allows it.

## Other apps

See [Interaction with other Apps](/app/docs/en/banking/interaction-with-other-apps) for how Banking works with ERPNext, HRMS, and related apps.
