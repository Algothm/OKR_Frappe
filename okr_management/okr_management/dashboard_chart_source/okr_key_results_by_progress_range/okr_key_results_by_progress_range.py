from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt
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
	rows = frappe.get_all("OKR Key Result", fields=["target_progress"], limit_page_length=10000)
	buckets = {"0-25%": 0, "26-50%": 0, "51-75%": 0, "76-100%": 0}
	for row in rows:
		progress = flt(row.target_progress)
		if progress <= 25:
			buckets["0-25%"] += 1
		elif progress <= 50:
			buckets["26-50%"] += 1
		elif progress <= 75:
			buckets["51-75%"] += 1
		else:
			buckets["76-100%"] += 1
	return {"labels": list(buckets), "datasets": [{"name": _("Key Results"), "values": list(buckets.values())}]}
