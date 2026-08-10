from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.dashboard import cache_source


@frappe.whitelist()
@cache_source
def get(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None, to_date=None, timespan=None, time_interval=None, heatmap_year=None):
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
