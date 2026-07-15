from __future__ import annotations

import frappe


def execute() -> None:
    if frappe.db.exists("Workflow", "OKR Objective Workflow"):
        frappe.delete_doc("Workflow", "OKR Objective Workflow", force=True, ignore_permissions=True)

    for workspace in ("Administration",):
        if frappe.db.exists("Workspace", workspace):
            frappe.delete_doc("Workspace", workspace, force=True, ignore_permissions=True)

    frappe.clear_cache()
