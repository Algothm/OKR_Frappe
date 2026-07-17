frappe.query_reports["Employee OKR Progress Report"] = {
	filters: [
		{fieldname: "plan", label: __("Plan"), fieldtype: "Link", options: "OKR Plan"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
	],
};
