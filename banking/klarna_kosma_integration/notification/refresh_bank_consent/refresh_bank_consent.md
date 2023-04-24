<div style="border: 1px solid #A6B1B9; border-radius: 4px; margin: 1rem;">
	<table
		class="panel-header" cellpadding="0" cellspacing="0" width="100%"
		style="border-spacing: 5px; font-size: 14px;"
	>
		<tr>
			<td width="30"></td>
			<td height="20"></td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td>
				<a href="{{ frappe.utils.get_url() }}">
					<img
						width="60"
						src="{{ app_logo_url }}"
						alt="app-logo" border="0"
						aria-hidden="true"
					>
				</a>
			</td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td height="20"></td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td>
				Hello,
			</td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td height="10"></td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td>
				<p>
					<b>Your Bank Consent for Bank <u>{{ doc.bank }}</u> and Company <u>{{ doc.company }}</u> expires in 7 days on {{ frappe.utils.global_date_format(doc.consent_expiry) }}.
					</b>
				</p>
				<p>
					To continue with automated Bank Transactions & Bank Accounts sync, go to Banking Settings and click on <b>Link Bank and Accounts</b>:
				</p>
			</td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td height="10"></td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td>
				<a
					href="{{ frappe.utils.get_url_to_form('Banking Settings', 'Banking Settings') }}"
					class="btn btn-primary btn-xs"
					target="_blank"
				>
					Renew Now
				</a>
			</td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td height="20"></td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td>
				<p style="color: #74808B; font-size: 12px;">
					Note: This is a system generated e-mail
				</p>
			</td>
			<td width="30"></td>
		</tr>
		<tr>
			<td width="30"></td>
			<td height="10"></td>
			<td width="30"></td>
		</tr>
	</table>
</div>
