from pathlib import Path

import frappe
from frappe.modules.import_file import import_file_by_path


def execute():
    if frappe.db.exists("Workspace", "OKR Action Item"):
        frappe.delete_doc("Workspace", "OKR Action Item", force=True, ignore_permissions=True)

    workspace_file = (
        Path(frappe.get_app_path("okr_management"))
        / "okr_management"
        / "workspace"
        / "okr_action_item_execution"
        / "okr_action_item_execution.json"
    )
    import_file_by_path(str(workspace_file), force=True, ignore_version=True)

    if frappe.db.exists("Workspace", "OKR Action Item Execution"):
        frappe.db.set_value(
            "Workspace", "OKR Action Item Execution", "icon", "clipboard", update_modified=False
        )

    if frappe.db.exists("Workspace", "Check-In"):
        frappe.db.set_value("Workspace", "Check-In", "sequence_id", 3.4, update_modified=False)

    frappe.clear_cache()
