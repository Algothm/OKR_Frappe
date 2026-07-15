frappe.query_reports["Employee OKR Progress Report"] = {
	filters: [
		{fieldname: "sprint", label: __("Sprint"), fieldtype: "Link", options: "OKR Sprint"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
	],
};
