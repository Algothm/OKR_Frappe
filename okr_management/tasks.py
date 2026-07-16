from __future__ import annotations

import frappe


def daily() -> None:
	publish_due_checkins()


def hourly() -> None:
	publish_at_risk_updates()


def publish_due_checkins() -> None:
	checkins = frappe.get_all("OKR Check In", filters={"status": ["=", "Draft"]}, pluck="name")
	for checkin in checkins:
		frappe.publish_realtime("okr_checkin_due", {"checkin": checkin})


def publish_at_risk_updates() -> None:
	items = frappe.get_all("OKR Key Result", filters={"status": "Active", "target_progress": ["<", 60]}, pluck="name")
	for item in items:
		frappe.publish_realtime("okr_key_result_at_risk", {"key_result": item})
