from __future__ import annotations

import frappe


def execute() -> None:
	"""Rename 'OKR Plan Planning' Workspace title and label from 'Plan' to 'OKR Planning'.

	NOTE: Clearing stale localStorage state (localStorage.current_page = "Plan") is NOT
	possible server-side in this migration patch because localStorage exists exclusively
	in user browsers. That client-side cleanup is handled defensively on page load by
	okr_management.js (Fix 3). This patch ensures database records reflect the new title/label.
	"""
	if frappe.db.exists("Workspace", "OKR Plan Planning"):
		frappe.db.set_value(
			"Workspace",
			"OKR Plan Planning",
			{
				"title": "OKR Planning",
				"label": "OKR Planning",
			},
			update_modified=False,
		)
	frappe.clear_cache()
