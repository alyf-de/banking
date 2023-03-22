<div align="center">
	<img src="https://user-images.githubusercontent.com/25857446/226990542-3fcef2dc-b6d0-41df-817e-c1641fabbe0b.png" height="80">
	<h2>ALYF Banking</h2>
</div>

<div align="center">
<p><b>ALYF Banking</b> is a seamless solution for connecting your bank accounts with ERPNext.</p>

<p>This app is designed to simplify your financial management by effortlessly fetching transactions from thousands of banks and integrating them directly into your ERPNext system. Say goodbye to manual data entry and time-consuming reconciliations ✨</p>

<p>Experience the ease of automation and gain better control over your finances with the ultimate banking integration app for ERPNext users.</p>
</div>

## Table of Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
- [Fetching a Bank and Bank Accounts](#fetching-a-bank-and-bank-accounts)
	- [Test Values](#test-values)
- [Fetching Bank Transactions](#fetching-bank-transactions)
	- [Manually Fetching/Syncing Transactions](#manually-fetchingsyncing-transactions)
	- [Automatic Transaction fetch/sync](#automatic-transaction-fetchsync)
- [Bank Consent (Important)](#bank-consent)


## Installation

1. Install [Bench](https://github.com/frappe/bench)
2. Install [ERPNext](https://github.com/frappe/erpnext)
3. `bench get-app https://github.com/alyf-de/banking.git`
4. `bench --site <sitename> install-app banking`

## Getting Started
> As an end user, you must get in touch with an authorized service provider who can provide you with the neccessary API Token to get started.

Go to **Klarna Kosma Settings**:
<img width="1309" alt="Screenshot 2022-12-19 at 3 39 06 PM" src="https://user-images.githubusercontent.com/25857446/208401464-5b508928-1098-4e57-9951-ad2467e6fab6.png">

- Once **Enabled** is checked, the **Client ID** and **API Token** (given by your service provider) must be filled in.
- If you are testing the APIs in a sandboxed environment, select `Playground` for the field **Klarna Kosma Environment**.
- **Save** and you are good to go.

## Fetching a Bank and Bank Accounts

The creation of a Bank and it's Bank Accounts are handled by the integration.

Click on the **Sync Bank and Accounts** button in the settings page, and follow the prompts.

<img width="75%" src="https://user-images.githubusercontent.com/25857446/208404531-6a292b38-385c-4eff-984c-b288f35b7d88.gif"/>

### Test values
- Select country as `Deutschland`
- Select `Demo Bank`
- Select Online Banking method as `Demo Bank PSD2`
- Username: `embedded`, Password: `12345`
- OTP: `12345`

For more test values and scenarios visit https://docs.openbanking.klarna.com/xs2a/test-bank-psd2.html

**The Bank and Bank Accounts will be created automatically at the end of the flow.**

> **Note:** This entire process of authentication with the Bank will be required once every quarter. More on this below

## Fetching Bank Transactions
Bank Transactions can be manually or automatically fetched/synced.

### Manually fetching/syncing transactions
Manually fetching transactions is currently only supported for one account at a time.

- Click on **Sync Transactions** in the settings page.
- Select the Bank Account whose transactions must be synced. Click on **Continue**

The transactions are enqueued to be fetched in the background. This job could be time consuming depending on the amount of transactions

### Automatic Transaction fetch/sync
By default a daily scheduled job will refresh Bank Accounts' data and fetch their transactions. This does not require any user intervention

**The transactions can be checked in the Bank Transactions List.**

> **Note:** The first bank transaction sync will consider the start date as the start of the current fiscal year

## Bank Consent

Once you finish syncing Bank and Bank Accounts by entering your bank credentials, you have essentially given the app consent (for a limited time) to access your bank accounts data.

Consent is stored in the form of a 'Bank Consent' record. The expiry of the consent is also visible in the Bank Consent record.

#### What data am I consenting to share?
You will be consenting to share:
- The list of accounts (and account data) under your bank customer ID (whose credentials you entered)
- Bank Transactions and their data (reference number, account, amount, counter party, etc.) linked to the accounts above, from the start of the current fiscal year

#### How long is the consent active for?
The consent expiry is set for 90 days from the day of creation (approximately 1 quarter). Until it expires, no user intervention is required to fetch data.

#### What do I do once the consent expires?
Once the consent expires, you will have to give explicit consent again by [resyncing bank and bank accounts](#fetching-a-bank-and-bank-accounts).

#### Is this consent token safe ?
It is safely encrypted and is also refreshed after every request that uses it.
