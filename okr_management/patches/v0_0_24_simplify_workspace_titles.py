from __future__ import annotations

import frappe


WORKSPACES = {
    "Plan": ("OKR Plan Planning", "OKR Plan", "OKR Plan Planning"),
    "Objective": ("OKR Objective Execution", "OKR Objective", "OKR Objective Execution"),
    "Key Result": ("OKR Key Result Execution", "OKR Key Result", "OKR Key Result Execution"),
    "Action Item": ("OKR Action Item Execution", "OKR Action Item", "OKR Action Item Execution"),
    "Check-In": ("Check-In", "OKR Check In", "Check-In"),
}


def execute():
    for current_name, (canonical_name, title, label) in WORKSPACES.items():
        workspace_name = canonical_name
        if current_name != canonical_name and frappe.db.exists("Workspace", current_name):
            if not frappe.db.exists("Workspace", canonical_name):
                frappe.rename_doc("Workspace", current_name, canonical_name, force=True)
        elif not frappe.db.exists("Workspace", canonical_name):
            continue

        frappe.db.set_value(
            "Workspace",
            workspace_name,
            {"title": title, "label": label},
            update_modified=False,
        )