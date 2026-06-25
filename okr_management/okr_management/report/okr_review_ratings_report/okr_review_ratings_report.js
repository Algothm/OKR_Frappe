frappe.query_reports["OKR Review Ratings Report"] = {
	filters: [
		{fieldname: "cycle", label: __("Cycle"), fieldtype: "Link", options: "OKR Cycle"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "review_status", label: __("Review Status"), fieldtype: "Select", options: "\nDraft\nSubmitted\nApproved\nModified\nRejected"},
	]
};
