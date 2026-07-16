frappe.query_reports["OKR Review Ratings Report"] = {
	filters: [
		{fieldname: "plan", label: __("Plan"), fieldtype: "Link", options: "OKR Plan"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "review_status", label: __("Review Status"), fieldtype: "Select", options: "\nDraft\nSubmitted\nApproved\nModified\nRejected"},
	]
};
