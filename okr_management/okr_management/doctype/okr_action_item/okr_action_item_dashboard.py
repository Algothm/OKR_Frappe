from frappe import _


def get_data():
	return {
		"fieldname": "action_item",
		"transactions": [
			{"label": _("Execution"), "items": ["OKR Check In"]},
		],
	}
