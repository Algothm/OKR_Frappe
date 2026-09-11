from frappe import _


def get_data():
	return {
		"fieldname": "parent_key_result",
		"transactions": [
			{"label": _("Execution"), "items": ["OKR Action Item"]},
		],
	}
