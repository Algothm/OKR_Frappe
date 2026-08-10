frappe.query_reports["At Risk OKR Report"] = {
	filters: [
		{fieldname: "plan", label: __("Plan"), fieldtype: "Link", options: "OKR Plan"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "days_to_end", label: __("Near End Days"), fieldtype: "Int", default: 14},
	],
};
