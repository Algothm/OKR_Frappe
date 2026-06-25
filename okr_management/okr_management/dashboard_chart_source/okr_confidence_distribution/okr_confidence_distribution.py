from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.dashboard import cache_source


@frappe.whitelist()
@cache_source
def get(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None, to_date=None, timespan=None, time_interval=None, heatmap_year=None):
	rows = frappe.get_all("OKR Objective", fields=["confidence", "count(name) as count"], group_by="confidence", order_by="confidence asc")
	labels = [str(row.confidence or _("Not Set")) for row in rows]
	values = [row.count for row in rows]
	return {"labels": labels, "datasets": [{"name": _("Objectives"), "values": values}]}
