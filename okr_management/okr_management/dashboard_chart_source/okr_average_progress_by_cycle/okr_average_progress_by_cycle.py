from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.dashboard import cache_source


@frappe.whitelist()
@cache_source
def get(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None, to_date=None, timespan=None, time_interval=None, heatmap_year=None):
	rows = frappe.get_all(
		"OKR Objective",
		fields=["cycle", "avg(progress) as progress"],
		filters={"cycle": ["is", "set"]},
		group_by="cycle",
		order_by="cycle asc",
		limit_page_length=10000,
	)
	return {"labels": [row.cycle for row in rows], "datasets": [{"name": _("Average Progress"), "values": [flt(row.progress, 2) for row in rows]}]}
