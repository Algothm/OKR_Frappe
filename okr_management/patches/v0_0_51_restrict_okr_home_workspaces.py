from __future__ import annotations

import frappe
from frappe.utils import cint


ADMIN_WORKSPACE = "OKR Admin Workspace Sidebar"
USER_WORKSPACE = "OKR Workspace Sidebar"
LEGACY_ADMIN_WORKSPACE = "OKR Admin Workspace"

WORKSPACE_ROLES = {
	ADMIN_WORKSPACE: ("OKR Admin", "System Manager"),
	USER_WORKSPACE: ("OKR User", "System Manager"),
}
PAGE_ROLES = {
	"okr-workspace": ("OKR User", "System Manager"),
}


def execute() -> None:
	sync_workspace_roles()
	sync_page_roles()
	changed_users = correct_invalid_admin_defaults()
	clear_workspace_caches(changed_users)


def sync_workspace_roles() -> None:
	for workspace_name, roles in WORKSPACE_ROLES.items():
		_sync_roles("Workspace", workspace_name, roles)


def sync_page_roles() -> None:
	for page_name, roles in PAGE_ROLES.items():
		_sync_roles("Page", page_name, roles)


def _sync_roles(parenttype: str, parent: str, roles: tuple[str, ...]) -> None:
	if not frappe.db.exists(parenttype, parent):
		return

	frappe.db.delete(
		"Has Role",
		{"parent": parent, "parenttype": parenttype, "parentfield": "roles"},
	)
	for index, role_name in enumerate(roles, start=1):
		role = frappe.new_doc("Has Role")
		role.update(
			{
				"parent": parent,
				"parenttype": parenttype,
				"parentfield": "roles",
				"idx": index,
				"role": role_name,
			}
		)
		role.db_insert()


def correct_invalid_admin_defaults() -> list[str]:
	changed_users = []
	users = frappe.get_all(
		"User",
		filters={"default_workspace": ["in", [LEGACY_ADMIN_WORKSPACE, ADMIN_WORKSPACE]]},
		fields=["name", "enabled", "user_type", "default_workspace"],
	)
	for user in users:
		roles = set(frappe.get_roles(user.name))
		is_enabled_system_user = cint(user.enabled) and user.user_type == "System User"
		if not is_enabled_system_user:
			new_default = None
		elif user.name == "Administrator" or roles & {"OKR Admin", "System Manager"}:
			new_default = ADMIN_WORKSPACE
		elif "OKR User" in roles:
			new_default = USER_WORKSPACE
		else:
			new_default = None

		if new_default != user.default_workspace:
			frappe.db.set_value(
				"User",
				user.name,
				"default_workspace",
				new_default,
				update_modified=False,
			)
			changed_users.append(user.name)

	return changed_users


def clear_workspace_caches(changed_users: list[str]) -> None:
	for workspace_name in WORKSPACE_ROLES:
		frappe.clear_document_cache("Workspace", workspace_name)
	for page_name in PAGE_ROLES:
		frappe.clear_document_cache("Page", page_name)
	for user in changed_users:
		frappe.clear_document_cache("User", user)

	# Public Workspace permissions and corrected defaults are both held in bootinfo.
	frappe.cache.delete_key("bootinfo")
