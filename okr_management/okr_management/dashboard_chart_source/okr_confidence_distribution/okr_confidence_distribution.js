frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["OKR Confidence Distribution"] = {
	method: "okr_management.okr_management.dashboard_chart_source.okr_confidence_distribution.okr_confidence_distribution.get",
	filters: [],
};
