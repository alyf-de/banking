// Copyright (c) 2022, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Klarna Kosma Settings', {
	refresh: (frm) => {
		if (frm.doc.enabled) {
			frm.add_custom_button(__('Link Bank and Accounts'), () => {
				frm.events.refresh_banks(frm);
			});

			frm.add_custom_button(__("Transactions"), () => {
				frm.events.sync_transactions(frm);
			}, __("Sync"));

			frm.add_custom_button(__("Older Transactions"), () => {
				frm.events.sync_transactions(frm, true);
			}, __("Sync"));
		}

	},

	refresh_banks: (frm) => {
		let fields = [{
			fieldtype: "Link",
			options: "Company",
			label: __("Company"),
			fieldname: "company",
			reqd: 1
		}];

		frappe.db.get_value(
			"Bank", {consent_id: ["is", "set"]}, "name"
		).then((result) => {
			if (!result.message.name) {
				// Prompt for start date if new setup
				fields.push({
					fieldtype: "Date",
					label: __("Start Date"),
					fieldname: "start_date",
					description: __("Access and Sync bank records from this date."),
					reqd: 1,
				});
			}

			frappe.prompt(fields, (data) => {
				new KlarnaKosmaConnect({
					frm: frm,
					flow: "accounts",
					company: data.company,
					start_date: data.start_date || null
				});
			},
			__("Setup Bank & Accounts Sync"),
			__("Continue"));
		});
	},

	sync_transactions: (frm, is_older=false) => {
		let fields = [
			{
				fieldtype: "Link",
				options: "Bank Account",
				label: __("Bank Account"),
				fieldname: "bank_account",
				reqd: 1,
				get_query: () => {
					return {
						filters: {
							"kosma_account_id": ["is", "set"],
						}
					};
				},
			},
			{
				fieldtype: "Section Break",
				fieldname: "sb_1",
			},
			{
				fieldtype: "Date",
				label: __("From Date"),
				fieldname: "from_date",
				reqd: 1
			},
			{
				fieldtype: "Column Break",
				fieldname: "cb_1",
			},
			{
				fieldtype: "Date",
				label: __("To Date"),
				fieldname: "to_date",
				reqd: 1
			},
			{
				fieldtype: "Section Break",
				fieldname: "sb_2",
				hide_border: 1
			},
			{
				fieldtype: "HTML",
				fieldname: "info"
			}
		];
		if (!is_older) {
			fields = fields.slice(0, 1);
		}

		let dialog = new frappe.ui.Dialog({
			title: is_older? __("Sync Older Transactions") : __("Sync Transactions"),
			fields: fields,
			primary_action_label: __("Sync"),
			primary_action: (data) => {
				dialog.hide();
				new KlarnaKosmaConnect({
					frm: frm,
					flow: "transactions",
					account: data.bank_account,
					from_date: is_older ? data.from_date : null,
					to_date: is_older ? data.to_date : null,
				});
			}
		});

		if (is_older) {
			dialog.get_field("info").$wrapper.html(
				`<div
					class="form-message blue"
					style="
						padding: var(--padding-sm) var(--padding-sm);
						background-color: var(--alert-bg-info);
					"
				>
					<span>${frappe.utils.icon("solid-info", "md")}</span>
					<span class="small" style="padding-left: 5px">
						Requires Bank Authentication
					</span>
				</div>`
			);
		}
		dialog.show();
	}
});

class KlarnaKosmaConnect {
	constructor(opts) {
		Object.assign(this, opts);
		this.use_flow_api = this.flow == "accounts" || (this.from_date && this.to_date);
		this.init_kosma_connect();
	}

	async init_kosma_connect () {
		if (this.use_flow_api) {
			// Renders XS2A App (which authenticates/gets consent)
			// and hands over control to server side for data fetch & business logic
			this.session = await this.get_client_token();
			this.render_xs2a_app();
		} else {
			// fetches data using the consent API without user intervention
			this.complete_transactions_flow();
		}
	}

	async get_client_token (){
		let session_data = await this.frm.call({
			method: "get_client_token",
			args: {
				current_flow: this.flow,
				account: this.account || null,
				from_date: this.flow === "accounts" ? this.start_date : this.from_date,
				to_date: this.to_date,
			},
			freeze: true,
			freeze_message: __("Please wait. Redirecting to Bank...")
		}).then(resp => resp.message);
		return session_data;
	}

	async render_xs2a_app() {
		// Render XS2A with client token
		await this.load_script();
		window.onXS2AReady = this.startKlarnaOpenBankingXS2AApp();
	}

	load_script() {
		return new Promise(function (resolve, reject) {
			const src = "https://x.klarnacdn.net/xs2a/app-launcher/v0/xs2a-app-launcher.js";

			if (document.querySelector('script[src="' + src + '"]')) {
				resolve();
				return;
			}

			const el = document.createElement('script');
			el.type = 'text/javascript';
			el.async = true;
			el.src = src;
			el.addEventListener('load', resolve);
			el.addEventListener('error', reject);
			el.addEventListener('abort', reject);
			document.head.appendChild(el);
		});
	}

	startKlarnaOpenBankingXS2AApp() {
		let me = this;
		try {
			window.XS2A.startFlow(
				me.session.client_token,
				{
					unfoldConsentDetails: true,
					onFinished: () => {
						if (me.flow === "accounts")
							me.complete_accounts_flow();
						else
							me.complete_transactions_flow();
					},
					onError: error => {
						console.error('onError: something bad happened.', error);
						// TODO: Log Error and End session
					},
					onAbort: () => {
						console.log("Kosma Authentication Aborted");
						// TODO: Log Error and End session
					},
				}
			)
		} catch (e) {
			console.error(e);
		}
	}

	async complete_accounts_flow() {
			let flow_data = await this.fetch_accounts_data();
			let bank_name = flow_data["message"]["bank_name"];

			this.add_bank_accounts(flow_data, bank_name);
	}

	async complete_transactions_flow()  {
		// Enqueue transactions fetch via Consent API
		await this.frm.call({
			method: "sync_transactions",
			args: {
				account: this.account,
				session_id_short: this.use_flow_api ? this.session.session_id_short : null
			},
			freeze: true,
			freeze_message: __("Please wait. Syncing Bank Transactions ...")
		});

	}

	async fetch_accounts_data() {
		try {
			const data = await this.frm.call({
				method: "fetch_accounts_and_bank",
				args: { session_id_short: this.session.session_id_short },
				freeze: true,
				freeze_message: __("Please wait. Fetching Bank Acounts ...")
			});

			if (!data.message || data.exc) {
				frappe.throw(__("Failed to fetch Bank Accounts."));
			}
			return data;
		} catch(e) {
			console.log(e);
		}
	}

	async add_bank_accounts(flow_data, bank_name) {
		let me = this;
		try {
			if (flow_data.message) {
				this.frm.call({
					method: "add_bank_accounts",
					args: {
						accounts: flow_data.message,
						company: me.company,
						bank_name: bank_name,
					},
					freeze: true,
					freeze_message: __("Adding Bank Acounts ...")
				}).then((r) => {
					if (!r.exc) {
						frappe.show_alert({ message: __("Bank accounts added"), indicator: 'green' });
					}
				});
			}
		} catch(e) {
			console.log(e);
		}
	}

}