from __future__ import annotations

import frappe

from okr_management.okr_management.doctype.okr_plan.okr_plan import get_period_label


def add_period_labels(key_results: list, action_items: list) -> None:
    """Attach derived fiscal Month/Quarter labels to KR and Action Item rows."""
    plan_names = {row.parent_plan for row in [*key_results, *action_items] if row.get("parent_plan")}
    plans = {
        row.name: row
        for row in frappe.get_all(
            "OKR Plan",
            filters={"name": ["in", list(plan_names)]},
            fields=["name", "financial_year", "sprint_frequency"],
        )
    } if plan_names else {}

    dated_rows = [(row, "end_date") for row in key_results] + [
        (row, "due_date") for row in action_items
    ]
    for row, date_field in dated_rows:
        plan = plans.get(row.get("parent_plan"))
        setattr(row, "period_label", get_period_label(row.get(date_field), plan) if plan else "")
