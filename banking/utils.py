import frappe
from frappe.utils import now_datetime
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete


def before_tests():
	# complete setup if missing
	year = now_datetime().year
	if not frappe.get_list("Company"):
		setup_complete(
			{
				"currency": "EUR",
				"full_name": "Test User",
				"company_name": "Wind Power LLC",
				"timezone": "Europe/Berlin",
				"company_abbr": "WP",
				"industry": "Manufacturing",
				"country": "Germany",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@erpnext.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)

	frappe.db.commit()  # nosemgrep
