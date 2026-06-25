frappe.query_reports["Cycle Review Report"] = {
	filters: [
		{fieldname: "cycle", label: __("Cycle"), fieldtype: "Link", options: "OKR Cycle"},
		{fieldname: "status", label: __("Cycle Status"), fieldtype: "Select", options: "
Draft
Pending Approval
Approved
Active
Review in Progress
Closed
Archived"},
	],
};
