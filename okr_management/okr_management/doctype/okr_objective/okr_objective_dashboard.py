from frappe import _


def get_data():
	return {
		"fieldname": "objective",
		"transactions": [
			{"label": _("Execution"), "items": ["OKR Key Result"]},
		],
	}