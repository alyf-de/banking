---
title: SEPA Payment Order
order: 50
roles:
  - Accounts User
  - Accounts Manager
---

The **SEPA Payment Order** feature provides a comprehensive solution for creating and managing SEPA Credit Transfer payments directly from ERPNext. This feature seamlessly integrates with **Purchase Invoice** to automate the payment process for suppliers and employees within the SEPA zone.

## Overview

SEPA Payment Orders enable users to:
- Create standardized SEPA Credit Transfer (pain.001) XML files
- Process multiple payments in a single batch
- Track payment status throughout the lifecycle
- Integrate seamlessly with EBICS for direct bank transmission
- Support both supplier and employee payments

## Key Features

### 1. Automated IBAN Validation
- All IBANs are validated using the `kontocheck` library
- Ensures compliance with IBAN standards before submission

### 2. Automatic BIC and Bank Name Resolution
- For German IBANs (starting with "DE"), the system automatically:
  - Determines the BIC/SWIFT code
  - Populates the bank name
- Reduces manual data entry and errors

### 3. Currency Validation
- Validates that payment currency matches the bank account currency
- Prevents currency mismatch errors before submission

### 4. Batch Processing Options
- _Process individually_: Each payment is handled as a separate transaction
- _Process as batch_: Multiple payments are bundled together for efficiency

> Important Note: Some banks may not properly consider the _Process individually_ setting (XML tag: `btchBookg`). If you experience issues where payments are still processed as a batch despite selecting _Process individually_, contact your bank for clarification on their batch booking handling.

### 5. Flexible Payment Scheduling
- Optional execution date for scheduled payments
- Reference number support for tracking

## How It Works

### Workflow Overview

1. Create: Generate a **SEPA Payment Order** from one or more **Purchase Invoice**
2. Review: Verify payment details and make any necessary adjustments
3. Submit: Approve the payment order for processing
4. Export: Download as XML or send directly to bank via EBICS
5. Track: Monitor payment status updates

## Creating SEPA Payment Orders

### From a Single Purchase Invoice

1. Navigate to a submitted **Purchase Invoice** that is not fully paid
2. Click on _Create_ → _SEPA Payment Order_
3. The system will:
   - Map outstanding payment schedule rows to SEPA payments
   - Auto-populate supplier/employee details
   - Set payment amounts based on outstanding balances

### From Multiple Purchase Invoices

1. Go to the **Purchase Invoice** list view
2. Select multiple unpaid invoices (must be submitted)
3. Click on _Actions_ → _SEPA Payment Order_
4. All selected invoices will be combined into a single payment order

### From an Expense Claim

1. Navigate to an approved **Expense Claim** that has not been fully reimbursed
2. Click on _Create_ → _SEPA Payment Order_
3. The system creates one payment row with the outstanding amount, directed at the employee's bank account

## SEPA Payment Order Details

### Header Information

- _Company_: The paying company
- _Bank Account_: Company's bank account for debiting
- _IBAN_: Automatically fetched from the selected bank account
- _Bank_: The company's bank
- _SWIFT Number_: Bank's SWIFT/BIC code

### Payment Options

- _Reference Number_: Optional reference for the entire payment order
- _Execution Date_: Optional future date for scheduled execution
- _Batch Booking_: Controls how payments are processed by the bank
  - _Process individually_: Each payment appears as a separate transaction in bank statements
  - _Process as batch_: Multiple payments are grouped as a single booking
  
  > Note about Batch Booking: This setting controls the `BtchBookg` flag in the SEPA XML file. However, some banks may not properly respect this setting and might still process payments as a batch even when _Process individually_ is selected. If you need individual transaction visibility in your bank statements and this setting doesn't work as expected, contact your bank to understand their batch booking policies. This setting's behavior may also relate to the C54 format settings configured in your **EBICS User** profile.

### Adding Recipients

You can add payment rows using the **Add Recipient** button (visible in draft state). This opens a dialog where you select:
- _DocType_: **Supplier** or **Employee**
- _Name_: The specific party
- Optionally: _Purpose_ and _Amount_

The system automatically fills in the recipient's name and IBAN from their default **Bank Account**. Adding a row in the payments grid also triggers this dialog.

### Payment Details (SEPA Payment Child Table)

Each payment row contains:
- _Recipient_: Name of the payee (supplier or employee)
- _IBAN_: Recipient's bank account number
- _SWIFT Number_: Recipient's bank BIC (auto-populated for German banks)
- _Bank Name_: Recipient's bank name
- _Amount_: Payment amount in the specified currency
- _Currency_: Payment currency (must match bank account currency)
- _Purpose_: Payment description (bill number for suppliers, custom text for employees)
- _EREF_: End-to-end reference (typically the invoice number)
- _Charges_: Fee allocation (SHAR=shared, DEBT=debtor pays, CRED=creditor pays)

### Reference Tracking

Each payment maintains links to:
- _Reference DocType_: The source document type (e.g., **Purchase Invoice**)
- _Reference Name_: The specific document ID
- _Reference Row Name_: The payment schedule row (for tracking partial payments)

## Payment Status Tracking

The system tracks four distinct statuses:

1. Draft: Payment order created but not yet approved
2. Approved: Payment order submitted and ready for transmission
3. Transmitted: Payment sent to bank (either downloaded or via EBICS)
4. Cancelled: Payment order cancelled

### Status Updates in Purchase Invoice

Payment status is automatically synchronized with the source **Purchase Invoice**:
- Updates appear in the **Payment Schedule** table
- Status changes trigger the `sepa_payment_order_status_changed` hook
- Provides real-time visibility of payment progress

## Integration with Purchase Invoice

### Custom Fields Added

The banking app adds several custom fields to **Purchase Invoice**:

- _Supplier Bank Account_: Link to the supplier's bank account
- _Employee Bank Account_: Link to the employee's bank account (for employee payments)
- _Create Supplier/Employee Bank Account_: Buttons for quick bank account creation

### Payment Schedule Enhancement

The **Payment Schedule** table includes:
- _SEPA Payment Order Status_: Shows the current status of any linked SEPA payment

### Automatic Data Mapping

When creating a **SEPA Payment Order** from **Purchase Invoice**:
- Outstanding amounts are calculated from the payment schedule
- Supplier/employee details are automatically populated
- Bank account information is fetched from linked records
- _Purpose_ field is set based on payment type

## Employee Payments

The system supports payment of **Purchase Invoices** to an **Employee** instead of to a **Supplier**. This can be related to a **Business Trip**, or independent, providing flexibility for expense reimbursements.

To enable payments to an **Employee**, a **Purchase Invoice** needs to meet these prerequisites:

- _Employee_ field populated
- _Pay to Employee_ checkbox enabled

## Bank Account Management

### Supplier Bank Accounts

The system can automatically:
- Create supplier bank accounts from **Purchase Invoice**
- Validate and store IBAN information
- Link bank accounts to suppliers for future use

### Company Bank Accounts

- Must be marked as _Is Company Account_
- Requires proper currency configuration
- Used as the debtor account for payments

## Export and Transmission

### Download as XML

After submitting a **SEPA Payment Order**:
1. Click on _Actions_ → _Download as XML_
2. The system generates a pain.001 compliant XML file
3. _Transmission Type_ is set to "DOWNLOADED"
4. Upload the file manually to your bank

### Send via EBICS (Currently Disabled)

Direct transmission to bank via EBICS:
1. Click on _Actions_ → _Send to Bank_
2. Select **EBICS User** and enter passphrases
3. The payment is uploaded to bank (unsigned)
4. _Transmission Type_ is set to "SENT_VIA_EBICS"
5. _EBICS Order ID_ is stored for reference

*Note: This feature is temporarily disabled and will be activated in a future update.*

## Technical Details

### Data Validation

- IBAN Validation: Uses the `kontocheck` library for comprehensive IBAN verification
- Currency Matching: Ensures payment currency matches the linked GL account currency
- Required Fields: Enforces all mandatory fields for SEPA compliance

### SEPA Compliance

- Generates pain.001.001.03 format XML files
- Supports SEPA Credit Transfer (SCT) scheme
- Handles both single and batch payments
- Complies with European Payments Council standards

### Hooks and Events

The **SEPA Payment Order** triggers the following events during its lifecycle:

1. **When Creating a Payment Order** (`after_insert`):
   - Triggered: After saving a new **SEPA Payment Order**
   - Action: Sets payment status to "Draft" in all linked documents
   - Notifies: All referenced documents (e.g., **Purchase Invoice**) via their `sepa_payment_order_status_changed` method

2. **When Submitting for Approval** (`on_submit`):
   - Triggered: When clicking _Submit_ on the **SEPA Payment Order**
   - Action: Updates payment status to "Approved" in all linked documents
   - Notifies: Updates the _SEPA Payment Order Status_ field in the **Payment Schedule** of linked **Purchase Invoice**

3. **When Transmitting to Bank** (`on_update_after_submit`):
   - Triggered: After downloading XML or sending via EBICS
   - Action: Updates payment status to "Transmitted" when `transmission_datetime` is set
   - Notifies: All linked documents receive the status update

4. **When Cancelling** (`on_cancel` or `on_trash`):
   - Triggered: When cancelling or deleting the **SEPA Payment Order**
   - Action: Clears payment status (sets to empty/cancelled) in all linked documents
   - Notifies: Removes the payment order reference from linked documents

#### How Other DocTypes Use These Events

When a status change occurs, the **SEPA Payment Order** calls the `sepa_payment_order_status_changed` method on each linked document. For example:

- **Purchase Invoice** implements this method to:
  - Update the _SEPA Payment Order Status_ field in its **Payment Schedule** table
  - Track which payments are in draft, approved, or transmitted state
  - Prevent duplicate payment orders for already processed payments

To implement this in your custom DocType, you have two options:

**Option 1: Add a method directly to your DocType class:**
```python
def sepa_payment_order_status_changed(self, payment_schedule_row_name, status):
    # Update your doctype's fields based on the new status
    # status will be one of: "", "Draft", "Approved", "Transmitted"
    pass
```

**Option 2: Use hooks (recommended for apps):**
In your app's `hooks.py`, add an entry to `doc_events`:
```python
doc_events = {
    "Your DocType Name": {
        "sepa_payment_order_status_changed": "your_app.path.to.module.function_name",
    },
}
```

Then implement the handler function:
```python
def sepa_payment_order_status_changed(doc, method, payment_schedule_row_name, status):
    # doc is the instance of your DocType
    # Update your doctype's fields based on the new status
    pass
```

The banking app itself uses the hooks approach for **Purchase Invoice** (see `banking/hooks.py`).

### Early Payment Discounts

When a **Purchase Invoice** has a payment schedule with discount terms, the **SEPA Payment Order** can calculate discounted amounts based on the _Execution Date_:

- If the execution date falls on or before the _Discount Date_ of a payment schedule row, the discounted amount is used
- If no execution date is set, or it falls after the discount date, the full outstanding amount applies
- Before submitting, the system warns if amounts have changed and prompts you to update them

### Security

- **System Manager** and **Accounts Manager**: Full access to all **SEPA Payment Orders**
- **Accounts User**: Can create, read, edit, and delete their own **SEPA Payment Orders** only
- Passphrase protection for EBICS transmission
- Audit trail via document versioning
- Read-only fields for system-generated data

## Best Practices

1. Set execution dates only when necessary (leave blank for immediate processing)
2. Maintain up-to-date bank account records for suppliers and employees

## Troubleshooting

### Common Issues

1. Currency Mismatch Error
   - Check that the payment currency matches the bank account's GL account currency
   - Verify the company bank account configuration

2. Missing Bank Account
   - Ensure suppliers/employees have bank accounts created
   - Use the quick creation buttons in **Purchase Invoice**

3. BIC Not Found (German IBANs)
   - Manually enter the BIC if automatic detection fails
