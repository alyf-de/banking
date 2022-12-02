// Copyright (c) 2022, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Klarna Kosma Settings', {
	refresh: function(frm) {
		if (frm.doc.enabled) {
			frm.add_custom_button(__('Link Bank Accounts'), () => {
				frappe.prompt({
					fieldtype: "Link",
					options: "Company",
					label: __("Company"),
					fieldname: "company",
					reqd: 1
				}, (data) => {
					new KlarnaKosmaConnect(frm, data.company);
				},
				__("Select a company"),
				__("Continue"));
			});

			// Button to Refresh Bank Accounts fetched (above flow again, rewrite existing data/add new)

			frm.add_custom_button(__("Sync Transactions"), () => {
				// fetch transactions (enqueue)
			})
		}

	}
});

class KlarnaKosmaConnect {
	// Renders XS2A App (which authenticates) and hands over control to server side to fetch data
	constructor(form_obj, company) {
		this.frm = form_obj;
		this.company = company;
		this.init_kosma_connect();
	}

	async init_kosma_connect () {
		this.session = await this.get_client_token();
		this.client_token = this.session.client_token;
		this.render_xs2a_app();
	}

	async get_client_token (){
		let session_data = await this.frm.call({
			method: "get_client_token",
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
				me.client_token,
				{
					onFinished: () => {
						me.complete_flow();
					},
					onError: error => {
						console.error('onError: something bad happened.', error)
					},
				}
			)
		} catch (e) {
			console.error(e)
		}
	}

	async complete_flow() {
			const flow_data = await this.fetch_flow_data();
			await this.add_bank_and_accounts(flow_data);
	}

	async fetch_flow_data() {
		let me = this;
		try {
			const data = await this.frm.call({
				method: "fetch_flow_data",
				args: {
					session_id: me.session.session_id,
					flow_id: me.session.flow_id
				},
				freeze: true,
				freeze_message: __("Please wait. Fetching Bank Acounts ...")
			});
			return data;
		} catch(e) {
			console.log(e);
			frappe.throw(__("Error fetching flow data. Check console."))
		}
	}

	async add_bank_and_accounts(flow_data) {
		let me = this;
		try {
			if (flow_data.message) {
				this.frm.call({
					method: "add_bank_and_accounts",
					args: {
						accounts: flow_data.message,
						company: me.company
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
			frappe.throw(__("Error adding bank and accounts. Check console."))
		}
	}

}