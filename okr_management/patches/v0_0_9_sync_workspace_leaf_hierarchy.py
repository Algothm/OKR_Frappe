from pathlib import Path

import frappe
from frappe.modules.import_file import import_file_by_path


WORKSPACE_FILES = [
    "okr_management/okr_management.json",
    "planning/planning.json",
    "execution/execution.json",
    "administration/administration.json",
]

OBSOLETE_LEAF_WORKSPACES = [
    "OKR Plan",
    "OKR Sprint",
    "Objectives",
    "Key Results",
    "OKR Settings",
    "OKR Approval Matrix",
]


def execute():
    for name in OBSOLETE_LEAF_WORKSPACES:
        if frappe.db.exists("Workspace", name):
            frappe.delete_doc("Workspace", name, force=True, ignore_permissions=True)

    base = Path(frappe.get_app_path("okr_management")) / "okr_management" / "workspace"
    for relative_path in WORKSPACE_FILES:
        import_file_by_path(str(base / relative_path), force=True, ignore_version=True)

    frappe.clear_cache()
