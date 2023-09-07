<div align="center">
	<img src="https://user-images.githubusercontent.com/25857446/226990542-3fcef2dc-b6d0-41df-817e-c1641fabbe0b.png" height="80">
	<h2>ALYF Banking</h2>
</div>

<div align="center">
<p><b>ALYF Banking</b> is a seamless solution for connecting your bank accounts with ERPNext.</p>

<p>This app is designed to simplify your financial management by effortlessly fetching transactions from thousands of banks and integrating them directly into your ERPNext system. Say goodbye to manual data entry and time-consuming reconciliations ✨</p>

<p>Experience the ease of automation and gain better control over your finances with the ultimate banking integration app for ERPNext users.</p>
</div>

**Note**: Our improved Bank Reconciliation Tool is free to use and compatible with other bank integrations. To connect your bank account, you'll need a paid subscription. Visit [banking.alyf.de](https://banking.alyf.de/banking-pricing) to check out the pricing and sign up.

## Table of Contents

- [Country and Bank Coverage](#country-and-bank-coverage)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [Fetching a Bank and Bank Accounts](#fetching-a-bank-and-bank-accounts)
	- [Test Values](#test-values)
- [Fetching Bank Transactions](#fetching-bank-transactions)
	- [Manually Fetching/Syncing Transactions](#manually-fetchingsyncing-transactions)
	- [Automatic Transaction fetch/sync](#automatic-transaction-fetchsync)
- [Bank Consent (Important)](#bank-consent)

## Country and Bank Coverage

Currently, we [support more than 15.000 banks from the following countries](https://portal.openbanking.klarna.com/bank-matrix).

- 🇦🇹 Austria
- 🇧🇪 Belgium
- 🇭🇷 Croatia
- 🇨🇿 Czech Republic
- 🇩🇰 Denmark
- 🇪🇪 Estonia
- 🇫🇮 Finland
- 🇫🇷 France
- 🇩🇪 Germany
- 🇭🇺 Hungary
- 🇮🇪 Ireland
- 🇮🇹 Italy
- 🇱🇻 Latvia
- 🇱🇹 Lithuania
- 🇱🇺 Luxembourg
- 🇲🇹 Malta
- 🇳🇱 Netherlands
- 🇳🇴 Norway
- 🇵🇱 Poland
- 🇵🇹 Portugal
- 🇷🇴 Romania
- 🇸🇰 Slovakia
- 🇪🇸 Spain
- 🇸🇪 Sweden
- 🇨🇭 Switzerland
- 🇬🇧 United Kingdom

## Installation

Install [via Frappe Cloud](https://frappecloud.com/marketplace/apps/banking) or on your local bench:

```bash
bench get-app https://github.com/alyf-de/banking.git
bench --site <sitename> install-app banking
```

## Getting Started
> As an end user, you must get in touch with an authorized service provider who can provide you with the neccessary API Token to get started.

Go to **Banking Settings**:

- Once **Enabled** is checked, the **Customer ID** and **API Token** (given by your service provider) must be filled in.
- **Save** and you are good to go.

## Fetching a Bank and Bank Accounts

The creation of a Bank and its Bank Accounts are handled by the integration.

Click on the **Sync Bank and Accounts** button on the settings page, and follow the prompts.

<img width="75%" src="https://user-images.githubusercontent.com/25857446/208404531-6a292b38-385c-4eff-984c-b288f35b7d88.gif"/>

### Test values
- Select the country as `Deutschland`
- Select `Demo Bank`
- Select the Online Banking method as `Demo Bank PSD2`
- Username: `embedded`, Password: `12345`
- OTP: `12345`

For more test values and scenarios visit https://docs.openbanking.klarna.com/xs2a/test-bank-psd2.html

**The Bank and Bank Accounts will be created automatically at the end of the flow.**

> **Note:** This entire process of authentication with the Bank will be required once every quarter. More on this below

## Fetching Bank Transactions
Bank Transactions can be manually or automatically fetched/synced.

### Manually fetching/syncing transactions
Manually fetching transactions is currently only supported for one account at a time.

- Click on **Sync Transactions** on the settings page.
- Select the Bank Account whose transactions must be synced. Click on **Continue**

The transactions are enqueued to be fetched in the background. This job could be time-consuming depending on the amount of transactions

### Automatic Transaction fetch/sync
By default, a daily scheduled job will refresh Bank Accounts' data and fetch their transactions. This does not require any user intervention

**The transactions can be checked in the Bank Transactions List.**

> **Note:** The first bank transaction sync will consider the start date as the start of the current fiscal year

## Bank Consent

Once you finish syncing Bank and Bank Accounts by entering your bank credentials, you have essentially given the app consent (for a limited time) to access your bank account's data.

Consent is stored in the form of a 'Bank Consent' record. The expiry of the consent is also visible in the Bank Consent record.

#### What data am I consenting to share?
You will be consenting to share:
- The list of accounts (and account data) under your bank customer ID (whose credentials you entered)
- Bank Transactions and their data (reference number, account, amount, counterparty, etc.) linked to the accounts above, from the start of the current fiscal year

#### How long is the consent active?
The consent expiry is set for 90 days from the day of creation (approximately 1 quarter). Until it expires, no user intervention is required to fetch data.

#### What do I do once the consent expires?
Once the consent expires, you will have to give explicit consent again by [resyncing bank and bank accounts](#fetching-a-bank-and-bank-accounts).

#### Is this consent token safe?
It is safely encrypted and is also refreshed after every request that uses it.

## Bank Reconciliation Tool

> Before using the tool, consider setting up ["Automatic Party Matching"](https://docs.erpnext.com/docs/user/manual/en/bank-reconciliation#3-2-3-automatic-party-matching-for-bank-transactions) to improve the reconciliation experience. Please go through the link to determine if this benefits your organisation.

<img src="https://raw.githubusercontent.com/alyf-de/banking/version-14/banking/public/images/bank_reco_tool.png" height="400">

Once all your Bank Transactions are synced into ERPNext, you can reconcile them with your existing vouchers. On your workspace sidebar, go to:

> Accounting > ALYF Banking > Bank Reconciliation

Or simply search for **Bank Reconciliation Tool Beta** in the awesomebar.

- Select a Company and Bank Account
- Make sure that the opening balance from ERPNext matches the opening balance of your Bank Statement.
- Enter the Closing Balance of the Bank Statement.
- Enter the date range to fetch unreconciled bank transactions

Once all the filters are set click on **Get Bank Transactions**.

You will now see the Bank Transactions on your left and the actions to perform on each transaction on your right.

The Transactions can be sorted based on various parameters. To proceed click on any Bank Transaction entry and perform any of the following actions:

### Update Transaction Details

You can update the Reference Number, Party and Party Type of a Bank Transaction or refer to it from the **Details** tab.

Simply fill in the fields in the 'Update' section and click on **Submit** at the bottom of the panel.

<img src="https://raw.githubusercontent.com/alyf-de/banking/version-14/banking/public/images/update_transaction.gif" height="300">

### Reconcile a Transaction

You can determine which vouchers you want to match against your Bank Transaction by checking the right filters within the **Match Voucher** tab.

<img src="https://raw.githubusercontent.com/alyf-de/banking/version-14/banking/public/images/match_transaction.png" height="300">

In the filters:
- **Purchase Invoice**: Fetches Purchase Invoices that have **Is Paid** checked. These are invoices that complete the payment cycle within the invoice itself (i.e. without a Payment Entry or Journal Entry against them).
- **Sales Invoice**: Fetches Sales Invoices against POS Invoices. Such Sales Invoices complete the accounting cycle themselves (i.e. without a Payment Entry or Journal Entry against them).
- **Bank Transaction**: Fetches Bank Transactions with the opposite impact as there might be a refund transaction.
- **Show Exact Party**: Is enabled and visible only if the Bank Transaction has a Party & Party Type set.
- **Unpaid Invoices**: Is visible only if 'Purchase Invoice' or 'Sales Invoice' is enabled. It fetches unpaid invoices for reconciliation.

The rest of the filters are self-explanatory.

The vouchers will be ranked on the basis of the number of fields matched. The match reason is visible on hovering over the '?' button.

You can match one or multiple vouchers against the same Bank Transaction using the checkboxes.

**On checking a voucher row**: The summary in the **Match Voucher** tab is updated. The checked rows sum up to the **Allocated Amount** and **To Allocate** shows how much in the Bank Transaction is left to reconcile.

Finally, after checking the desired rows, click on the **Reconcile** at the bottom of the panel.
- If the transaction is fully reconciled, it will be removed and the next transaction will be auto-focused.
- If the transaction is partially reconciled, the view stays the same except the **Allocated Amount** will be permanently updated. Now you can continue to finish reconciling this transaction or move on to another one.

> The tool helps you reconcile with **unpaid invoices** by automatically creating a payment against the invoice and reconciling said payment against the Bank Transaction.

### Create a Voucher

If there are no matching vouchers against your Bank Transaction you can also create a **Payment Entry** or **Journal Entry** against it.

<img src="https://raw.githubusercontent.com/alyf-de/banking/version-14/banking/public/images/create_voucher.png" height="300">

- Go to the **Create Voucher** tab
- Fill in any mandatory or otherwise missing details
- Click on **Create** at the bottom of the panel.

A voucher will be automatically created, **submitted** and fully reconciled against the current Bank Transaction.

If you want to edit more details in the voucher to be created, you can click on **Edit in Full Page** and you will be redirected to the voucher in the **Draft** state. You can edit this voucher and submit it.

### Auto Reconcile

The **Auto Reconcile** button at the very top of the tool automatically reconciles Bank Transactions and vouchers that have matching reference numbers.

The reconciliation will occur within the limits of the account and date filters that are set.