frappe.query_reports["At Risk OKR Report"] = {
	filters: [
		{fieldname: "cycle", label: __("Cycle"), fieldtype: "Link", options: "OKR Cycle"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "days_to_end", label: __("Near End Days"), fieldtype: "Int", default: 14},
	],
};
