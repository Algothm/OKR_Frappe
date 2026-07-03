from frappe import _


def get_data():
	return {
		"fieldname": "sprint",
		"transactions": [
			{"label": _("Execution"), "items": ["OKR Objective"]},
		],
	}