frappe.query_reports["OKR Health Insights Report"] = {
	filters: [
		{fieldname: "plan", label: __("Plan"), fieldtype: "Link", options: "OKR Plan"},
		{fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department"},
		{fieldname: "owner", label: __("Owner"), fieldtype: "Link", options: "User"},
		{fieldname: "risk_level", label: __("Risk Level"), fieldtype: "Select", options: "\nCritical\nHigh\nMedium\nLow"},
		{fieldname: "type", label: __("Type"), fieldtype: "Select", options: "\nObjective\nKey Result"},
		{fieldname: "only_due_soon", label: __("Only Upcoming Deadlines"), fieldtype: "Check", default: 0},
		{fieldname: "only_missed_checkins", label: __("Only Missed Check-ins"), fieldtype: "Check", default: 0},
	]
};
