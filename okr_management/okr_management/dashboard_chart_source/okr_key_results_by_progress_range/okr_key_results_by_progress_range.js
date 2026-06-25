frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["OKR Key Results by Progress Range"] = {
	method: "okr_management.okr_management.dashboard_chart_source.okr_key_results_by_progress_range.okr_key_results_by_progress_range.get",
	filters: [],
};
