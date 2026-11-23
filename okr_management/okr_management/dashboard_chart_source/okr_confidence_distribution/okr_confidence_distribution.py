from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.dashboard import cache_source

from okr_management.permissions import require_okr_admin


@frappe.whitelist()
def get(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None, to_date=None, timespan=None, time_interval=None, heatmap_year=None):
	require_okr_admin()
	return _get(
		chart_name=chart_name,
		chart=chart,
		no_cache=no_cache,
		filters=filters,
		from_date=from_date,
		to_date=to_date,
		timespan=timespan,
		time_interval=time_interval,
		heatmap_year=heatmap_year,
	)


@cache_source
def _get(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None, to_date=None, timespan=None, time_interval=None, heatmap_year=None):
	rows = frappe.get_all("OKR Objective", fields=["confidence", "count(name) as count"], group_by="confidence", order_by="confidence asc")
	labels = [str(row.confidence or _("Not Set")) for row in rows]
	values = [row.count for row in rows]
	return {"labels": labels, "datasets": [{"name": _("Objectives"), "values": values}]}
