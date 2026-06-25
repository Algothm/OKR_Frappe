frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["OKR Average Progress by Cycle"] = {
	method: "okr_management.okr_management.dashboard_chart_source.okr_average_progress_by_cycle.okr_average_progress_by_cycle.get",
	filters: [],
};
