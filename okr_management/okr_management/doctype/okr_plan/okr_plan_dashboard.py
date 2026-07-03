from frappe import _


def get_data():
	return {
		"fieldname": "parent_plan",
		"transactions": [
			{"label": _("Planning"), "items": ["OKR Sprint"]},
			{"label": _("Execution"), "items": ["OKR Objective"]},
		],
	}