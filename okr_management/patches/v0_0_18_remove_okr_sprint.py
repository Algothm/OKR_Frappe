from __future__ import annotations

import json

import frappe


OBSOLETE_DOCTYPE = "OKR Sprint"


def execute() -> None:
    migrate_plan_relationships()
    remove_workspace_references()
    remove_dependent_metadata()
    if frappe.db.exists("DocType", OBSOLETE_DOCTYPE):
        frappe.delete_doc("DocType", OBSOLETE_DOCTYPE, force=True, ignore_permissions=True)
    frappe.clear_cache()


def migrate_plan_relationships() -> None:
    if not frappe.db.table_exists(OBSOLETE_DOCTYPE):
        return

    if frappe.db.table_exists("OKR Objective") and frappe.db.has_column("OKR Objective", "parent_plan"):
        frappe.db.sql(
            """
            update `tabOKR Objective` objective
            inner join `tabOKR Sprint` sprint on sprint.name = objective.sprint
            set objective.parent_plan = sprint.parent_plan
            where ifnull(objective.parent_plan, '') = ''
            """
        )

    relationships = (
        ("OKR Key Result", "objective", "OKR Objective"),
        ("OKR Action Item", "parent_key_result", "OKR Key Result"),
        ("OKR Check In", "key_result", "OKR Key Result"),
    )
    for child, link_field, parent in relationships:
        if (
            frappe.db.table_exists(child)
            and frappe.db.table_exists(parent)
            and frappe.db.has_column(child, "parent_plan")
            and frappe.db.has_column(parent, "parent_plan")
        ):
            frappe.db.sql(
                f"""
                update `tab{child}` child
                inner join `tab{parent}` parent on parent.name = child.`{link_field}`
                set child.parent_plan = parent.parent_plan
                where ifnull(child.parent_plan, '') = ''
                """
            )


def remove_workspace_references() -> None:
    for child_doctype in ("Workspace Link", "Workspace Shortcut"):
        if frappe.db.table_exists(child_doctype):
            frappe.db.delete(child_doctype, {"link_to": OBSOLETE_DOCTYPE})

    for workspace_name in ("OKR Sprint", "OKR Sprint Planning"):
        if frappe.db.exists("Workspace", workspace_name):
            frappe.delete_doc("Workspace", workspace_name, force=True, ignore_permissions=True)

    for name in frappe.get_all("Workspace", pluck="name"):
        workspace = frappe.get_doc("Workspace", name)
        changed = False
        for fieldname in ("links", "shortcuts"):
            rows = workspace.get(fieldname) or []
            retained = [
                row for row in rows
                if row.get("link_to") != OBSOLETE_DOCTYPE
                and row.get("label") != OBSOLETE_DOCTYPE
            ]
            if len(retained) != len(rows):
                workspace.set(fieldname, retained)
                changed = True
        if workspace.content:
            try:
                content = json.loads(workspace.content)
            except (TypeError, ValueError):
                content = []
            retained = [
                item for item in content
                if item.get("data", {}).get("shortcut_name") != OBSOLETE_DOCTYPE
                and item.get("data", {}).get("link_to") != OBSOLETE_DOCTYPE
            ]
            if retained != content:
                workspace.content = json.dumps(retained)
                changed = True
        if changed:
            workspace.flags.ignore_permissions = True
            workspace.save()


def remove_dependent_metadata() -> None:
    if frappe.db.table_exists("Dashboard Chart"):
        frappe.db.delete("Dashboard Chart", {"document_type": OBSOLETE_DOCTYPE})
    if frappe.db.table_exists("Number Card"):
        frappe.db.delete("Number Card", {"document_type": OBSOLETE_DOCTYPE})
    if frappe.db.table_exists("Report"):
        frappe.db.delete("Report", {"ref_doctype": OBSOLETE_DOCTYPE})
    if frappe.db.table_exists("Notification"):
        frappe.db.delete("Notification", {"document_type": OBSOLETE_DOCTYPE})
    if frappe.db.table_exists("Workflow"):
        frappe.db.delete("Workflow", {"document_type": OBSOLETE_DOCTYPE})
