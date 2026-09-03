from __future__ import annotations

import frappe


def is_okr_admin(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	return bool({"OKR Admin", "System Manager"} & roles)


def is_okr_user(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	return bool({"OKR User", "System Manager"} & roles)


def _is_plan_team_member(plan_name: str, user: str) -> bool:
	return bool(
		frappe.db.exists(
			"OKR Plan Team Member",
			{
				"parent": plan_name,
				"parenttype": "OKR Plan",
				"parentfield": "members",
				"member_user": user,
			},
		)
	)


def get_plan_permission_query_conditions(user: str | None = None) -> str:
	"""Only OKR Admins (and System Managers) can view/manage OKR Plans."""
	user = user or frappe.session.user
	if is_okr_admin(user):
		return ""
	return "1=0"


def has_plan_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Plan access is strictly OKR Admin only."""
	user = user or frappe.session.user
	return is_okr_admin(user)
