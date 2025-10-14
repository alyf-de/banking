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


## Multi-Currency Reconciliation Behaviour

### Key Currency Field Relationships

**Invoice Currency Fields:**
- `outstanding_amount`: Always in **company currency** (e.g., INR), regardless of invoice currency
- `grand_total`: In **invoice currency** (e.g., USD, EUR, GBP)
- `base_grand_total`: Invoice amount converted to **company currency** (e.g., INR)
- `party_account_currency`: Currency of the receivable/payable account used
- `conversion_rate`: Exchange rate from invoice currency to company currency

**Bank Transaction Fields:**
- `currency`: Bank account currency (can be different from company currency)
- `unallocated_amount`: In bank account currency
- `deposit`/`withdrawal`: In bank account currency
- `payment_entries[].allocated_amount`: In **bank account currency** (not company currency!)

### Cross-Currency Reconciliation Logic

**When Bank Currency = Company Currency (e.g., INR bank, INR company):**

1. **Invoice Matching** (`bank_reconciliation_tool_beta.py` lines 1092-1141):
   - If `bank_currency == company_currency`: Use `outstanding_amount` for matching
   - If `bank_currency != company_currency`: Use `grand_total` for matching
   - **Constraint**: Cross-currency requires `outstanding_amount == base_grand_total` (full invoice only)

2. **Payment Entry Creation** (`unpaid_vouchers.py` lines 135-192):
   - Calls `get_payment_entry()` from ERPNext with `bank_account` parameter
   - Clears references, then calls `adjust_and_allocate_invoices()`
   - Sets amounts:
     - For `Receive`: `paid_amount = sum(allocated_amount)`, `received_amount = bt.allocated_amount`
     - For `Pay`: `received_amount = sum(allocated_amount)`, `paid_amount = bt.allocated_amount`
   - **Both amounts are in company currency (INR)** when bank is in company currency
   - Sets exchange rate: `source_exchange_rate` or `target_exchange_rate` depending on payment type

3. **Allocation Logic** (`unpaid_vouchers.py` lines 261-308):
   - Calculates `row_allocated_amount` in bank currency
   - Converts to company currency: `row.allocated_amount = row_allocated_amount * conversion_rate`
   - **Result**: `allocated_amount` in Payment Entry Reference is always in **company currency**

### Payment Entry Multi-Currency Structure

**Example: USD Invoice (100 USD) + INR Bank (9000 INR), conversion_rate=90**

```
Payment Entry:
  payment_type: "Receive"
  paid_from: Debtors - _TC (receivable account)
  paid_from_account_currency: INR (from invoice.party_account_currency)
  paid_to: Bank Account - _TC (bank account)
  paid_to_account_currency: INR
  paid_amount: 9000 (in paid_from_account_currency = INR)
  received_amount: 9000 (in paid_to_account_currency = INR)
  
  references[0]:
    reference_name: SI-00001
    allocated_amount: 9000 INR (always in company currency!)

Bank Transaction:
  payment_entries[0]:
    allocated_amount: 9000 (in bank account currency = INR)
```

**Example: USD Invoice (100 USD) + USD Bank (100 USD), conversion_rate=90**

```
Invoice:
  grand_total: 100 USD
  base_grand_total: 9000 INR (100 * 90)
  party_account_currency: INR (receivable account is in company currency)

Payment Entry:
  payment_type: "Receive"
  paid_from: Debtors - _TC (receivable account in INR)
  paid_from_account_currency: INR
  paid_to: USD Bank Account - _TC (bank account in USD)
  paid_to_account_currency: USD
  paid_amount: 9000 (in paid_from_account_currency = INR)
  received_amount: 100 (in paid_to_account_currency = USD)
  
  references[0]:
    reference_name: SI-00001
    allocated_amount: 9000 INR (always in company currency!)

Bank Transaction:
  currency: USD
  deposit: 100 USD
  payment_entries[0]:
    allocated_amount: 100 (in bank account currency = USD)
```

**Key Insight**: 
- Payment Entry `paid_amount` is in `paid_from_account_currency`
- Payment Entry `received_amount` is in `paid_to_account_currency`
- Payment Entry `references[].allocated_amount` is in **company currency (INR)**
- Bank Transaction `payment_entries[].allocated_amount` is in **bank account currency**

**Important**: The Payment Entry's paid/received amounts depend on which accounts are used (paid_from and paid_to), not directly on invoice or company currency.

### Journal Entry Multi-Currency Structure

**For multi-party reconciliation** (`unpaid_vouchers.py` lines 76-132):
- Creates Journal Entry instead of Payment Entry
- **Constraint**: All account currencies must match bank account currency
- Sets `multi_currency = 1` if any account currency differs from company currency
- All amounts in `accounts[]` are in company currency (converted via `allocated_amount`)

### Testing Multi-Currency Scenarios

**Test Setup:**
- Company: "_Test Company" with currency **INR**
- Conversion rates: USD=90 INR, EUR=100 INR
- Use `party_account_currency` from invoice to verify Payment Entry account currencies

**Common Test Pattern:**
```python
# Create USD customer and invoice
usd_customer = create_customer("Customer", currency="USD")
si = create_sales_invoice(rate=100, currency="USD", conversion_rate=90, ...)

# Create INR bank transaction matching base_grand_total
bt = create_bank_transaction(deposit=si.base_grand_total, currency="INR", ...)

# Reconcile
bulk_reconcile_vouchers(bt.name, json.dumps([{"payment_doctype": "Sales Invoice", "payment_name": si.name}]))

# Verify amounts
self.assertEqual(si.grand_total, 100.0)  # USD
self.assertEqual(si.base_grand_total, 9000.0)  # INR
self.assertEqual(pe.paid_amount, 9000.0)  # INR
self.assertEqual(pe.references[0].allocated_amount, 9000.0)  # INR (not USD!)
```

### Important Constraints

1. **Full Invoice Only for Cross-Currency**: 
   - Lines 1140-1141, 1333-1334: `outstanding_amount == base_grand_total`
   - **Critical**: This constraint is ONLY applied when `bank_currency != company_currency`
   - Partial payments not supported for cross-currency reconciliation
   - **Scenarios**:
     - ✅ EUR bank + USD invoice (constraint applied): Only full invoices matched
     - ✅ INR bank + USD invoice (constraint NOT applied): Partial invoices can be matched
     - The constraint protects against exchange rate issues when bank ≠ company currency

2. **Multi-Currency Flag**:
   - Line 592: `common_filters.multi_currency = "multi_currency" in document_types`
   - Controls whether cross-currency invoices are matched
   - **Without flag**: Query filters to `invoice.currency == bank.currency` (line 1134)
   - **With flag**: Allows matching invoices in different currency (lines 1136-1141)
   - Example: To match USD invoice with INR bank, flag must be enabled

3. **Journal Entry Currency Validation**:
   - Lines 82-87 in `unpaid_vouchers.py`: Account currencies must match for Journal Entry creation
   - Multi-party multi-currency requires all accounts in same currency as bank

4. **Return Invoice Handling** (`unpaid_vouchers.py` lines 179-190):
   - For `Pay` type: `received_amount = abs(sum(allocated_amount))`, `paid_amount = bt.allocated_amount`
   - For `Receive` type: `paid_amount = abs(sum(allocated_amount))`, `received_amount = bt.allocated_amount`
   - The `abs()` function ensures Payment Entry amounts are always positive
   - However, `references[].allocated_amount` remains negative for return invoices

## Test Case Corrections (October 2025)

During test review, three critical issues were identified and corrected:

### 1. Return Invoice Amount Handling (`test_usd_return_invoice_inr_bank`)

**Issue**: Test had ambiguous expectations for Payment Entry amounts with return invoices.

**Resolution**: 
- Clarified that `abs()` is applied per `unpaid_vouchers.py` lines 179-183
- Payment Entry amounts (`paid_amount`, `received_amount`) are positive even for returns
- Only `references[].allocated_amount` remains negative (-9000 INR)
- This is correct behavior per the spec

### 2. Cross-Currency Constraint Test (`test_cross_currency_full_amount_constraint`)

**Issue**: Original test used INR bank + USD invoice, but constraint wasn't triggered.

**Root Cause**: 
- Constraint `outstanding_amount == base_grand_total` only applies when `bank_currency != company_currency`
- Original test: INR bank = INR company → constraint NOT applied ❌
- The constraint is meant to protect against exchange rate issues when converting bank currency to company currency

**Resolution**:
- Changed to EUR bank + USD invoice (both ≠ INR company)
- Now constraint IS applied ✅
- Test verifies partially paid invoices are excluded when `bank_currency != company_currency`
- Properly creates partial payment to violate constraint (outstanding: 4500, base_grand_total: 9000)

### 3. Multi-Currency Flag Behavior (`test_multi_currency_flag_in_get_linked_payments`)

**Issue**: Test only checked that results were booleans, didn't verify actual behavior.

**Resolution**:
- Added explicit assertions with clear failure messages
- **Without flag**: USD invoice NOT found for INR bank (currency filter applied)
- **With flag**: USD invoice IS found for INR bank (cross-currency enabled)
- Verifies matched invoice meets constraint (`paid_amount == base_grand_total`)

### Key Learnings

1. **Constraint Application**: The cross-currency constraint is currency-pair-specific:
   - Applied when: `bank_currency ≠ company_currency`
   - Not applied when: `bank_currency = company_currency` (even if invoice currency differs)

2. **Multi-Currency Flag**: Essential for cross-currency reconciliation:
   - Enables matching invoices with currency different from bank currency
   - Works in conjunction with the full-invoice constraint

3. **Test Design**: Cross-currency tests must use appropriate currency combinations:
   - Use non-company-currency bank accounts to trigger constraints
   - Verify both positive (constraint satisfied) and negative (constraint violated) cases