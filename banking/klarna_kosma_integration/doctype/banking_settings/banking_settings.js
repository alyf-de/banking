// Copyright (c) 2022, ALYF GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Banking Settings", {
	setup: (frm) => {
		frm.trigger("set_voucher_matching_defaults_query");
	},
	set_voucher_matching_defaults_query: async (frm) => {
		const document_types = await frappe.xcall(
			"erpnext.accounts.doctype.bank_transaction.bank_transaction.get_doctypes_for_bank_reconciliation"
		);
		frm.set_query("voucher_matching_defaults", (doc) => {
			return {
				filters: {
					name: ["in", document_types],
				},
			};
		});
	},
	refresh: (frm) => {
		if (frm.doc.enabled) {
			frm.trigger("get_app_health");

			if (frm.doc.enable_ebics) {
				frm.add_custom_button(__("View EBICS Users"), () => {
					frappe.set_route("List", "EBICS User");
				});
			}

			if (frm.doc.customer_id && frm.doc.admin_endpoint && frm.doc.api_token) {
				frm.trigger("get_subscription");
			}

			frm.add_custom_button(__("Open Billing Portal"), async () => {
				const url = await frm.call({
					method: "get_customer_portal_url",
					freeze: true,
					freeze_message: __("Redirecting to Customer Portal ..."),
				});
				if (url.message) {
					window.open(url.message, "_blank");
				}
			});
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

		frm.doc.reference_fields.map((field) => {
			set_field_options(frm, field.doctype, field.name);
		});
	},

	get_subscription: async (frm) => {
		const data = await frm.call({
			method: "fetch_subscription_data",
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
					margin-bottom: 0.5rem;
				">
					<p style="font-weight: 700; font-size: 16px;">
						${__("Subscription Details")}
					</p>
					<p>
						<b>${__("Subscriber")}</b>:
						${subscription.full_name}
					</p>
					<p>
						<b>${__("Status")}</b>:
						${subscription.subscription_status}
					</p>
					<p>
						<b>${__("Ebics Users")}</b>:
						${subscription.ebics_usage.used} (${__("Usage")}) / ${
				subscription.ebics_usage.allowed
			} (${__("Limit")})
					</p>
					<p>
						<b>${__("Valid Till")}</b>:
						${frappe.format(subscription.plan_end_date, { fieldtype: "Date" })}
					</p>
					<p>
						<b>${__("Last Renewed On")}</b>:
						${frappe.format(subscription.last_paid_on, { fieldtype: "Date" })}
					</p>
					<p>
						<a
							href="${subscription.billing_portal}"
							target="_blank"
							class="${subscription.billing_portal ? "" : "hidden"}"
						>
							<b>${__("Open Billing Portal")}</b>
							${frappe.utils.icon("link-url", "sm")}
						</a>
					</p>
				</div>
			`);

			if (subscription.billing_portal) {
				frm.remove_custom_button(__("Open Billing Portal"));
			}

			frm.refresh_field("subscription");
		}
	},

	get_app_health: async (frm) => {
		const data = await frm.call({
			method: "get_app_health",
		});

		let messages = data.message;
		if (messages) {
			if (messages["info"]) {
				frm.set_intro(messages["info"], "blue");
			}

			if (messages["warning"]) {
				$(frm.$wrapper.find(".form-layout")[0]).prepend(`
					<div class='form-message yellow'>
						${messages["warning"]}
					</div>
				`);
			}
		}
	},
});

frappe.ui.form.on("Banking Reference Mapping", {
	reference_fields_add: (frm, cdt, cdn) => {
		set_field_options(frm, cdt, cdn);
	},

	document_type: (frm, cdt, cdn) => {
		set_field_options(frm, cdt, cdn);
	},
});

function set_field_options(frm, cdt, cdn) {
	const doc = frappe.get_doc(cdt, cdn);
	const document_type = doc.document_type || "Sales Invoice";

	// set options for `field_name`
	frappe.model.with_doctype(document_type, () => {
		const meta = frappe.get_meta(document_type);
		const fields = meta.fields.filter((field) => {
			return (
				["Link", "Data"].includes(field.fieldtype) && field.is_virtual === 0
			);
		});

		frm.fields_dict.reference_fields.grid.update_docfield_property(
			"field_name",
			"options",
			fields
				.map((field) => {
					return {
						value: field.fieldname,
						label: __(field.label),
					};
				})
				.sort((a, b) => a.label.localeCompare(b.label))
		);
		frm.refresh_field("reference_fields");
	});
}

function get_info_html(message) {
	return `<div
		class="form-message blue"
		style="
			padding: var(--padding-sm) var(--padding-sm);
			background-color: var(--alert-bg-info);
		"
	>
		<span>${frappe.utils.icon("solid-info", "md")}</span>
		<span class="small" style="padding-left: var(--padding-xs)">
			${message}
		</span>
	</div>`;
}
