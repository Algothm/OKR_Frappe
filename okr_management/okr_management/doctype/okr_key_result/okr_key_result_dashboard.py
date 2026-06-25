from frappe import _


def get_data():
    return {
        "fieldname": "key_result",
        "transactions": [
            {"label": _("Execution"), "items": ["OKR Action Item"]},
        ],
    }
