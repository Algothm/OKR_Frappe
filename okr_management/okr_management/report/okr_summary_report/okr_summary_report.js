frappe.query_reports["OKR Summary Report"] = {
	filters: [
		{fieldname: "cycle", label: __("Cycle"), fieldtype: "Link", options: "OKR Cycle"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "status", label: __("Status"), fieldtype: "Data"},
	],
};
