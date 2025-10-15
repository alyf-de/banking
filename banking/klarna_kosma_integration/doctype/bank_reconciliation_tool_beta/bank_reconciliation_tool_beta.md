# Bank Reconciliation Tool Beta Testing Guide

A comprehensive guide for testing the Bank Reconciliation Tool's behavior and edge cases.

## Testing Match Tab Voucher Visibility

### Withdrawal Bank Transactions

The visibility of vouchers depends on which filters are checked:

**Purchase Invoice Matching:**
- With _Unpaid Invoices_ checked: Shows unpaid Purchase Invoices (outstanding ≠ 0), including returns, plus unpaid return Sales Invoices
- Without _Unpaid Invoices_ checked: Shows paid Purchase Invoices (`is_paid = 1`) that lack a clearance date

**Sales Invoice Matching:**
- With _Unpaid Invoices_ checked: Shows unpaid Sales Invoices (outstanding ≠ 0), including returns, plus unpaid return Purchase Invoices
- Without _Unpaid Invoices_ checked: Shows Sales Invoices without clearance dates that were paid via POS

**Expense Claim Matching:**
- Shows unpaid expense claims
- Only visible when _Unpaid Vouchers_ filter is checked

**Other Voucher Types:**
- Visibility depends solely on whether the corresponding doctype filter is checked

## Multi-Currency Reconciliation Testing

### Understanding Currency Fields

**Invoice Currency Fields:**
- `outstanding_amount`: In the party account currency (currency of the receivable/payable account)
- `grand_total`: In the invoice's own currency (e.g., USD, EUR, GBP)
- `base_grand_total`: In company's default currency (all `base_*` fields are in company currency)
- `party_account_currency`: Currency of the receivable/payable account used
- `conversion_rate`: Exchange rate from invoice currency to party account currency

**Bank Transaction Fields:**
- `currency`: Bank account currency (may differ from company currency)
- `unallocated_amount`, `deposit`, `withdrawal`: All in bank account currency
- `payment_entries[].allocated_amount`: In bank account currency

### How Currency Matching Works

**When Bank Currency Equals Company Currency:**
- Invoice matching uses `outstanding_amount` for comparison
- Both Payment Entry amounts are in company currency
- Partial payments are allowed

**When Bank Currency Differs from Company Currency:**
- Invoice matching uses `grand_total` for comparison
- Requires full invoice amount: `outstanding_amount == base_grand_total`
- Partial payments are NOT allowed (prevents exchange rate issues)
- Must enable multi-currency flag to match invoices in different currencies

### Payment Entry Structure Examples

**Example 1: USD Invoice with INR Bank**
- Invoice: 100 USD (9000 INR base_grand_total at rate 90)
- Bank Transaction: 9000 INR
- Payment Entry:
  - `paid_amount`: 9000 INR (in receivable account currency)
  - `received_amount`: 9000 INR (in bank account currency)
  - `references[].allocated_amount`: 9000 INR (in receivable account currency)
  - Bank Transaction `allocated_amount`: 9000 INR

**Example 2: USD Invoice with USD Bank**
- Invoice: 100 USD (9000 INR base at rate 90)
- Bank Transaction: 100 USD
- Payment Entry:
  - `paid_amount`: 9000 INR (in receivable account currency)
  - `received_amount`: 100 USD (bank account in USD)
  - `references[].allocated_amount`: 9000 INR (in receivable account currency)
  - Bank Transaction `allocated_amount`: 100 USD

**Key Rule**: Payment Entry `paid_amount` and `received_amount` follow the currencies of `paid_from` and `paid_to` accounts respectively. The `references[].allocated_amount` is in the receivable/payable account currency (party account currency).

### Journal Entry Considerations

For multi-party reconciliation:
- Creates Journal Entry instead of Payment Entry
- All account currencies must match the bank account currency
- Sets `multi_currency = 1` if any account differs from company currency
- All `accounts[]` amounts are converted to company currency

### Testing Multi-Currency Scenarios

**Recommended Test Setup:**
- Company currency: INR
- Test currencies: USD (rate: 90), EUR (rate: 100)
- Create matching bank accounts in each currency

**Common Test Pattern:**
```python
# Create invoice in foreign currency
customer = create_customer("Test Customer", currency="USD")
invoice = create_sales_invoice(
    rate=100, 
    currency="USD", 
    conversion_rate=90
)

# Create bank transaction matching base_grand_total
bt = create_bank_transaction(
    deposit=invoice.base_grand_total,
    currency="INR"
)

# Perform reconciliation
bulk_reconcile_vouchers(
    bt.name, 
    json.dumps([{
        "payment_doctype": "Sales Invoice",
        "payment_name": invoice.name
    }])
)

# Verify currency conversions
assert invoice.grand_total == 100.0  # USD
assert invoice.base_grand_total == 9000.0  # INR
assert payment_entry.paid_amount == 9000.0  # INR
assert payment_entry.references[0].allocated_amount == 9000.0  # Party account currency
```

### Critical Constraints to Test

**1. Full Invoice Requirement for Cross-Currency:**
- Applies only when bank currency ≠ company currency
- Invoices must be fully outstanding: `outstanding_amount == base_grand_total`
- Partially paid invoices are excluded to avoid exchange rate complexities
- Test scenarios:
  - ✅ EUR bank + USD invoice: Constraint applies (only full invoices match)
  - ✅ INR bank + USD invoice: Constraint does NOT apply (partial matching allowed)

**2. Multi-Currency Flag:**
- Controls whether cross-currency invoice matching is enabled
- Without flag: Only matches invoices where `invoice.currency == bank.currency`
- With flag: Allows matching invoices in different currencies (with constraints)
- Test both states to verify filtering behavior

**3. Journal Entry Currency Validation:**
- For multi-party reconciliation via Journal Entry
- All accounts must be in the same currency as the bank account
- Validation fails if account currencies don't match

**4. Return Invoice Handling:**
- Payment Entry amounts (`paid_amount`, `received_amount`) are always positive
- Uses `abs()` on summed allocated amounts
- However, `references[].allocated_amount` remains negative for returns
- Ensures proper accounting while maintaining sign in references

### Testing Return Invoices

When testing return/credit note scenarios:
- Verify Payment Entry amounts are positive values
- Check that reference allocated amounts are negative
- Test with both same-currency and cross-currency setups
- Confirm exchange rates are applied correctly

### Cross-Currency Test Checklist

To properly test cross-currency constraints:
- [ ] Use a bank account in a currency different from company currency (e.g., EUR bank with INR company)
- [ ] Create invoices in a third currency (e.g., USD)
- [ ] Test with fully outstanding invoices (should match)
- [ ] Test with partially paid invoices (should NOT match)
- [ ] Verify multi-currency flag enables/disables cross-currency matching
- [ ] Check that same-currency bank accounts (INR bank + INR company) allow partial payments regardless of invoice currency

### Common Testing Pitfalls

**Pitfall 1: Wrong Currency Combination**
- Using bank currency = company currency won't trigger cross-currency constraints
- Use EUR or USD bank accounts for proper cross-currency testing

**Pitfall 2: Ambiguous Test Expectations**
- Clearly distinguish between Payment Entry amounts (always positive) and reference amounts (can be negative)
- Verify both the Payment Entry fields and Bank Transaction allocated amounts

**Pitfall 3: Missing Flag Verification**
- Always test both with and without multi-currency flag enabled
- Verify expected behavior changes between states

**Pitfall 4: Partial Payment Scenarios**
- Create actual partial payments (not just modified outstanding amounts)
- Verify constraint applies based on bank currency vs company currency relationship

### Best Practices for Test Design

1. **Use Descriptive Test Names**: Include currencies involved (e.g., `test_usd_invoice_eur_bank_full_amount_only`)

2. **Test Currency Combinations Systematically**:
   - Same currency: INR invoice + INR bank
   - Invoice differs: USD invoice + INR bank
   - Bank differs: USD invoice + EUR bank
   - All differ: USD invoice + EUR bank + INR company

3. **Verify All Amount Fields**: Check `grand_total`, `base_grand_total`, `outstanding_amount`, `paid_amount`, `received_amount`, and all allocated amounts

4. **Test Both Positive and Negative Cases**: Verify both successful matches and expected failures

5. **Include Edge Cases**: Returns, partial payments, multi-party reconciliation, exchange rate variations

6. **Assert with Clear Messages**: Use descriptive assertion messages that explain what behavior is being verified
