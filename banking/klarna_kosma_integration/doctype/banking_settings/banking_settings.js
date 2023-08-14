// Copyright (c) 2022, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Banking Settings', {
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

			frm.add_custom_button(__("View Subscription"), () => {
				frm.events.get_subscription(frm);
			}, __("Actions"));

			frm.add_custom_button(__("Handle Subscription"), async () => {
				const url = await frm.call({
					method: "get_customer_portal_url",
					freeze: true,
					freeze_message: __("Redirecting to Customer Portal ...")
				});
				if (url.message) {
					window.open(url.message, "_blank");
				}
			}, __("Actions"));
		} else {
			frm.page.add_inner_button(
				__("Signup for Banking"),
				() => {
					window.open(`${frm.doc.admin_endpoint}/banking-pricing`, "_blank");
				},
				null,
				"primary"
			);
		}
	},

	refresh_banks: (frm) => {
		let fields = [
			{
				fieldtype: "Link",
				options: "Company",
				label: __("Company"),
				fieldname: "company",
				reqd: 1
			},
			{
				fieldtype: "Date",
				label: __("Start Date (Optional)"),
				fieldname: "start_date",
				description: __("Access and Sync bank records from this date."),
			}
		];

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
	},

	get_subscription: async (frm) => {
		const data = await frm.call({
			method: "fetch_subscription_data",
			freeze: true,
			freeze_message: __("Please wait. Fetching Subscription Details ...")
		});

		if (data.message) {
			let subscription = data.message[0];

			frm.get_field("subscription").$wrapper.empty();
			frm.doc.subscription = "subscription";
			frm.get_field("subscription").$wrapper.html(`
				<div
					style="border: 1px solid var(--gray-300);
					border-radius: 4px;
					padding: 1rem;
					width: calc(50% - 15px);
					margin-bottom: 0.5rem;
				">
					<p style="font-weight: 700; font-size: 16px;">
						${ __("Subscription Details") }
					</p>
					<p>Subscriber: <u>${subscription.full_name}</u></p>
					<p>Status: <u>${subscription.subscription_status}</u></p>
					<p>Transaction Limit: <u>${subscription.transaction_limit}</u></p>
					<p>Valid Till: <u>${subscription.plan_end_date}</u></p>
					<p>Last Renewed On: <u>${subscription.last_paid_on}</u></p>
				</div>
			`);
			frm.refresh_field("subscription");
		}
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
						console.error('Something bad happened.', error);
						if (!error) {
							error = {"message": __("Something bad happened.")}
						}
						me.handle_failed_xs2a_flow(error);
					},
					onAbort: error => {
						console.error("Kosma Authentication Aborted", error);
						if (!error) {
							error = {"message": __("Kosma Authentication Aborted")}
						}
						me.handle_failed_xs2a_flow(error);					},
				}
			)
		} catch (e) {
			console.error(e);
		}
	}

	async complete_accounts_flow() {
			let flow_data = await this.fetch_accounts_data();
			if (!flow_data) return;

			flow_data = flow_data["message"];

			if (!flow_data["bank_data"] || !flow_data["accounts"]) return;
			this.add_bank_accounts(flow_data);
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
				args: {
					session_id_short: this.session.session_id_short,
					company: this.company,
				},
				freeze: true,
				freeze_message: __("Please wait. Fetching Bank Acounts ...")
			});

			if (!data.message || data.exc) {
				frappe.throw(__("Failed to fetch Bank Accounts."));
			} else {
				return data;
			}
		} catch(e) {
			console.log(e);
		}
	}

	async add_bank_accounts(flow_data) {
		let me = this;
		try {
			this.frm.call({
				method: "add_bank_accounts",
				args: {
					accounts: flow_data["accounts"],
					company: me.company,
					bank_name: flow_data["bank_data"]["bank_name"],
				},
				freeze: true,
				freeze_message: __("Adding Bank Acounts ...")
			}).then((r) => {
				if (!r.exc) {
					frappe.show_alert({ message: __("Bank accounts added"), indicator: 'green' });
				}
			});
		} catch(e) {
			console.log(e);
		}
	}

	handle_failed_xs2a_flow(error) {
		try {
			frappe.call({
				method: "banking.klarna_kosma_integration.exception_handler.handle_ui_error",
				args: {
					error: error,
					session_id_short: this.session.session_id_short
				}
			}).then((r) => {
				if (!r.exc) {
					frappe.show_alert({ message: __("Session Ended"), indicator: "red" });
				}
			});
		} catch(e) {
			console.log(e);
		}
	}
}
