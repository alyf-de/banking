# Bank Reconciliation Tool Beta Behaviours

Cases and expected behaviours for clarity in testing


## Match Tab Visible Vouchers

### Withdrawal Bank Transaction

Depending on multiple checked filters:
- **Purchase Invoice**:
    - _Unpaid Invoices_: Unpaid PInvs including returns(outstanding >< 0), Unpaid **return** SInvs
    - _Without Unpaid Invoices_: PInvs with `is_paid` checked and no clearance date (among other basic filters)
- **Sales Invoice**:
    - _Unpaid Invoices_: Unpaid SInvs including returns(outstanding >< 0), Unpaid **return** PInvs
    - _Without Unpaid Invoices_: SInvs with no clearance date and paid via POS (among other basic filters)
- **Expense Claim**: Unpaid expense claims. Visible only if _Unpaid Vouchers_ is checked

The rest is self explanatory and _only depends on the doctype filter being checked_.