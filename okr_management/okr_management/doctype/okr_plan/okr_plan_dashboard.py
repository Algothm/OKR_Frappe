from frappe import _


def get_data():
	return {
		"fieldname": "parent_plan",
		"transactions": [
			{"label": _("Execution"), "items": ["OKR Objective"]},
		],
	}