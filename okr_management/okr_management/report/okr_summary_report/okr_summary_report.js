frappe.query_reports["OKR Summary Report"] = {
	filters: [
		{fieldname: "sprint", label: __("Sprint"), fieldtype: "Link", options: "OKR Sprint"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "status", label: __("Status"), fieldtype: "Data"},
	],
};
