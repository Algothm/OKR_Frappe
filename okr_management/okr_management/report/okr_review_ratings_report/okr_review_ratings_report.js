frappe.query_reports["OKR Review Ratings Report"] = {
	filters: [
		{fieldname: "sprint", label: __("Sprint"), fieldtype: "Link", options: "OKR Sprint"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "review_status", label: __("Review Status"), fieldtype: "Select", options: "\nDraft\nSubmitted\nApproved\nModified\nRejected"},
	]
};
