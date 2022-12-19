<div align="center">
	<img src="https://user-images.githubusercontent.com/25857446/208396676-9b9c83ed-50fd-4db8-8463-e1faf9884306.svg" height="128">
	<h2>Klarna Kosma Integration</h2>
</div>

This app integrates Klarna Kosma's Open Banking API with ERPNext. 

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
3. `bench get-app https://github.com/alyf-de/klarna_kosma_integration.git`
4. `bench --site <sitename> install-app klarna_kosma_integration`
5. `bench --site <sitename> migrate`

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

Consent is stored in the form of a token in the Bank record. The expiry of the consent is also visible
<img width="75%" alt="Screenshot 2022-12-19 at 4 20 19 PM" src="https://user-images.githubusercontent.com/25857446/208409779-96192e5d-91f0-45df-b8cf-0df92a1e81dd.png">

#### What data am I consenting to share?
You will be consenting to share: 
- The list of accounts (and account data) under your bank customer ID (whose credentials you entered)
- Bank Transactions and their data (reference number, account, amount, counter party, etc.) linked to the accounts above, from the start of the current fiscal year

#### How long is the consent active for?
The consent expiry is set for 90 days from the day of creation (approximately 1 quarter). Until it expires, no user intervention is required to fetch data.

#### What do I do once the consent expires?
Once the consent expires, you will have to give explicit consent again by [resyncing bank and bank accounts](#fetching-a-bank-and-bank-accounts).

#### Is this consent token safe ?
It is safely encrypted and is also exchanged with Klarna Kosma after every request that uses it.
