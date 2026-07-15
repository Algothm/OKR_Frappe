from __future__ import annotations

import frappe


REMOVED_DOCTYPES = (
    "OKR Progress Update",
    "OKR Cycle Review",
    "OKR Score Snapshot",
    "OKR Approval Matrix",
    "OKR Settings",
    "OKR Action Item Row",
    "OKR Cycle",
    "OKR Initiative",
)

REMOVED_REPORTS = (
    "Approval Aging",
    "Department Rollup",
    "Cycle Review Report",
    "OKR Cycle Summary",
    "OKR Summary",
)


def execute() -> None:
    migrate_action_item_checkins()
    migrate_objective_reviews_to_sprints()
    remove_obsolete_metadata()


def migrate_action_item_checkins() -> None:
    if not frappe.db.table_exists("OKR Action Item Row") or not frappe.db.has_column("OKR Check In", "action_item"):
        return
    frappe.db.sql(
        """
        update `tabOKR Check In` ci
        inner join `tabOKR Action Item Row` row
            on row.parent = ci.name
            and row.parenttype = 'OKR Check In'
            and row.parentfield = 'action_items'
        set ci.action_item = row.action_item_id
        where ifnull(ci.action_item, '') = ''
          and ifnull(row.action_item_id, '') != ''
        """
    )


def migrate_objective_reviews_to_sprints() -> None:
    if not frappe.db.table_exists("OKR Objective Review") or not frappe.db.has_column("OKR Objective Review", "sprint"):
        return
    if frappe.db.has_column("OKR Objective Review", "cycle") and frappe.db.table_exists("OKR Cycle"):
        frappe.db.sql(
            """
            update `tabOKR Objective Review` review
            inner join `tabOKR Cycle` cycle on cycle.name = review.cycle
            inner join `tabOKR Sprint` sprint
                on sprint.company = cycle.company
                and sprint.start_date = cycle.start_date
                and sprint.end_date = cycle.end_date
            set review.sprint = sprint.name
            where ifnull(review.sprint, '') = ''
            """
        )
    frappe.db.sql(
        """
        update `tabOKR Objective Review` review
        inner join `tabOKR Objective` objective on objective.name = review.objective
        set review.sprint = objective.sprint
        where ifnull(review.sprint, '') = ''
        """
    )


def remove_obsolete_metadata() -> None:
    if frappe.db.exists("Workflow", "OKR Objective Workflow"):
        frappe.delete_doc("Workflow", "OKR Objective Workflow", force=True, ignore_permissions=True)

    for report in REMOVED_REPORTS:
        if frappe.db.exists("Report", report):
            frappe.delete_doc("Report", report, force=True, ignore_permissions=True)

    for doctype in REMOVED_DOCTYPES:
        if frappe.db.exists("DocType", doctype):
            frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)

    frappe.clear_cache()
