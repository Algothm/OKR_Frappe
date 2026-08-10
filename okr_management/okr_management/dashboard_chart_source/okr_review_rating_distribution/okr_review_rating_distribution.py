from __future__ import annotations

import frappe
from frappe import _
from frappe.utils.dashboard import cache_source
from frappe.utils import flt


@frappe.whitelist()
@cache_source
def get(chart_name=None, chart=None, no_cache=None, filters=None, from_date=None, to_date=None, timespan=None, time_interval=None, heatmap_year=None):
	rows = frappe.get_all(
		"OKR Objective Review",
		filters={"manager_rating": [">", 0], "docstatus": ["<", 2]},
		fields=["manager_rating"]
	)

	rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
	for row in rows:
		val = int(round(flt(row.manager_rating) * 5.0))
		if val in rating_counts:
			rating_counts[val] += 1

	stars_map = {
		5: "★★★★★",
		4: "★★★★",
		3: "★★★",
		2: "★★",
		1: "★"
	}

	labels = [stars_map[r] for r in [5, 4, 3, 2, 1]]
	values = [rating_counts[r] for r in [5, 4, 3, 2, 1]]

	return {
		"labels": labels,
		"datasets": [{"name": _("Reviews"), "values": values}]
	}
