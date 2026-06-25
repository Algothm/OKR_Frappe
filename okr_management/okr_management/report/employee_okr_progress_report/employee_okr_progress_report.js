frappe.query_reports["Employee OKR Progress Report"] = {
	filters: [
		{fieldname: "cycle", label: __("Cycle"), fieldtype: "Link", options: "OKR Cycle"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
	],
};
