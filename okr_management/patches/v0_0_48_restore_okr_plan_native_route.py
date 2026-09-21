from __future__ import annotations

import frappe


WORKSPACE_LAYOUT = {
	"OKR Admin Workspace Sidebar": {
		"title": "OKR Admin Workspace",
		"label": "OKR Admin Workspace",
		"parent_page": "",
		"sequence_id": 2.0,
	},
	"OKR Plan Planning": {
		"title": "OKR Plan",
		"label": "OKR Plan",
		"parent_page": "OKR Admin Workspace",
		"sequence_id": 2.1,
	},
	"OKR Workspace Sidebar": {
		"title": "OKR Workspace",
		"label": "OKR Workspace",
		"parent_page": "",
		"sequence_id": 3.0,
	},
	"OKR Objective Execution": {
		"title": "Objective",
		"label": "Objective",
		"parent_page": "OKR Workspace",
		"sequence_id": 3.1,
	},
	"OKR Key Result Execution": {
		"title": "Key Result",
		"label": "Key Result",
		"parent_page": "OKR Workspace",
		"sequence_id": 3.2,
	},
	"Action Item": {
		"title": "OKR Action Item",
		"label": "OKR Action Item",
		"parent_page": "OKR Workspace",
		"sequence_id": 3.3,
	},
	"Check-In": {
		"title": "OKR Check In",
		"label": "OKR Check In",
		"parent_page": "OKR Workspace",
		"sequence_id": 3.4,
	},
}


def execute() -> None:
	"""Restore native OKR routes and the intended deterministic sidebar hierarchy."""
	for workspace_name, values in WORKSPACE_LAYOUT.items():
		if frappe.db.exists("Workspace", workspace_name):
			frappe.db.set_value(
				"Workspace",
				workspace_name,
				values,
				update_modified=False,
			)
	frappe.clear_cache()