frappe.query_reports["OKR Summary Report"] = {
	filters: [
		{fieldname: "plan", label: __("Plan"), fieldtype: "Link", options: "OKR Plan"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "status", label: __("Status"), fieldtype: "Data"},
	],
};
