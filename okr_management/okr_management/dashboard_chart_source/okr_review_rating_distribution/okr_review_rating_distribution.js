frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["OKR Review Rating Distribution"] = {
	method: "okr_management.okr_management.dashboard_chart_source.okr_review_rating_distribution.okr_review_rating_distribution.get",
	filters: [],
};
