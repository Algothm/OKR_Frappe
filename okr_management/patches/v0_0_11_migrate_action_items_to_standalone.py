from __future__ import annotations

import frappe
from frappe.model.naming import make_autoname


def execute() -> None:
    if not frappe.db.exists("DocType", "OKR Action Item"):
        return

    # Find all child action items
    # They have parenttype == 'OKR Key Result'
    child_items = frappe.db.sql(
        """
        select name, parent, action_item_title, owner_user, status, progress, due_date, description, priority, notes, start_date
        from `tabOKR Action Item`
        where parenttype = 'OKR Key Result' and parent is not null and parent != ''
        """,
        as_dict=True,
    )

    for item in child_items:
        # Check if already migrated to avoid duplicates
        exists = frappe.db.exists(
            "OKR Action Item",
            {
                "parent_key_result": item.parent,
                "action_item_title": item.action_item_title,
                "owner_user": item.owner_user,
                "parenttype": ["is", "not set"],
            },
        )
        if exists:
            continue

        parent_kr = frappe.db.get_value(
            "OKR Key Result",
            item.parent,
            ["objective", "parent_sprint", "parent_plan", "company", "department", "financial_year"],
            as_dict=True,
        )

        if not parent_kr:
            continue

        # Map status appropriately to the new options list:
        # Open, In Progress, Blocked, Completed, Cancelled
        status = item.status
        if status in ("Draft", "Planned"):
            status = "Open"
        elif status in ("Closed", "Archived"):
            status = "Completed"
        elif status not in ("Open", "In Progress", "Blocked", "Completed", "Cancelled"):
            status = "Open"

        # Create new standalone Action Item document
        standalone_ai = frappe.get_doc({
            "doctype": "OKR Action Item",
            "action_item_title": item.action_item_title,
            "parent_key_result": item.parent,
            "parent_objective": parent_kr.objective,
            "parent_sprint": parent_kr.parent_sprint,
            "parent_plan": parent_kr.parent_plan,
            "company": parent_kr.company,
            "department": parent_kr.department,
            "financial_year": parent_kr.financial_year,
            "owner_user": item.owner_user,
            "status": status,
            "progress": item.progress or 0.0,
            "due_date": item.due_date,
            "start_date": item.start_date,
            "description": item.description,
            "priority": item.priority or "Medium",
            "notes": item.notes,
        })
        # Set naming series and name
        standalone_ai.naming_series = "OKR-ACT-.YYYY.-"
        standalone_ai.name = make_autoname("OKR-ACT-.YYYY.-")
        standalone_ai.db_insert()
        print(f"Migrated action item: {item.action_item_title} to standalone document: {standalone_ai.name}")

    frappe.db.commit()
