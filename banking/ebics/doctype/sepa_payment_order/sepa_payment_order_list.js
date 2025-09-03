frappe.listview_settings["SEPA Payment Order"] = {
	add_fields: ["transmission_type"],
	get_indicator: function (doc) {
		if (doc.transmission_type === "DOWNLOADED") {
			return [
				__("Downloaded"),
				"green",
				"transmission_type,=," + doc.transmission_type,
			];
		}
		if (doc.transmission_type === "SENT_VIA_EBICS") {
			return [
				__("Sent via EBICS"),
				"green",
				"transmission_type,=," + doc.transmission_type,
			];
		}
		if (doc.docstatus === 1) {
			return [__("Approved"), "blue", "docstatus,=," + doc.docstatus];
		}

		return [__("Draft"), "red", "docstatus,=," + doc.docstatus];
	},
};
