from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from okr_management.utils.okr_calculations import recalculate_objective_progress, recalculate_plan_progress
from okr_management.okr_management.doctype.okr_plan.okr_plan import get_plan_timeline


STATUS_TRANSITIONS = {
    "Draft": {"Active"},
    "Active": {"On Hold", "Completed"},
    "On Hold": {"Active", "Completed"},
    "Completed": {"Closed"},
    "Closed": set(),
}

SETUP_LOCKED_STATUSES = {"Active", "On Hold", "Completed", "Closed"}
ACTIVE_LOCKED_STATUSES = {"Active", "On Hold", "Completed", "Closed"}
PLAN_ACTIVE_REQUIRED_STATUSES = {"Active", "On Hold", "Completed", "Closed"}
COMPLETED_KR_STATUSES = {"Achieved", "Completed", "Closed"}
GOVERNANCE_ROLES = {"OKR Admin", "OKR Manager"}
MANAGER_ROLES = {"OKR Admin", "OKR Manager", "Department Head"}

SETUP_LOCKED_FIELDS = {
    "parent_plan",
    "financial_year",
    "company",
    "department",
    "level_details",
    "teams",
    "plan_owner",
    "level",
    "start_date",
    "end_date",
}
ACTIVE_LOCKED_FIELDS = {"objective_title", "owner_user"}
SYSTEM_FIELDS = {"progress", "key_result_count"}


class OKRObjective(Document):
    def before_validate(self) -> None:
        self.status = self.status or "Draft"
        self.priority = self.priority or "High"
        self.level = self.level or "Department"
        self.sync_level_details()
        self.owner_user = self.owner_user or frappe.session.user
        self.inherit_context_from_plan()
        self.default_dates_from_plan()
        self.update_system_summary_fields()

    def validate(self) -> None:
        self.validate_required_fields()
        self.validate_parent_relationships()
        self.validate_lifecycle_transition()
        self.validate_parent_status_dependencies()
        self.validate_dates_inside_plan()
        self.validate_child_dates()
        self.validate_duplicate_title_in_plan()
        self.validate_completion_criteria()
        self.validate_locked_fields()
        self.validate_system_fields()

    def on_update(self) -> None:
        values = self.get_system_summary_values()
        if values:
            frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
        recalculate_plan_progress(self.parent_plan)

    def on_trash(self) -> None:
        if self.has_key_results():
            frappe.throw(_("Cannot delete Objective because Key Results exist."))

    def get_invalid_links(self, is_submittable=False):
        # Dynamic Links are checked before before_validate during insert.
        self.sync_level_details()
        return super().get_invalid_links(is_submittable=is_submittable)

    def exists_in_database(self) -> bool:
        return bool(self.name and frappe.db.exists(self.doctype, self.name))

    def sync_level_details(self) -> None:
        doctypes = {"Department": "Department", "Team": "User", "Individual": "User"}
        self.level_details_doctype = doctypes.get(self.level)
        if self.level == "Organization":
            self.level_details = None
            self.department = None
        elif self.level == "Individual":
            self.level_details = self.level_details or frappe.session.user
            self.department = None
        elif self.level == "Department":
            self.level_details = self.level_details or self.department
            self.department = self.level_details
        else:
            self.department = None

    def inherit_context_from_plan(self) -> None:
        if not self.parent_plan or not frappe.db.exists("OKR Plan", self.parent_plan):
            return

        plan = frappe.db.get_value(
            "OKR Plan", self.parent_plan,
            ["financial_year", "company", "owner_user", "status"],
            as_dict=True,
        )
        if not plan:
            return

        self.financial_year = plan.financial_year
        self.company = plan.company
        self.plan_owner = plan.owner_user

    def default_dates_from_plan(self) -> None:
        if not self.parent_plan or not frappe.db.exists("OKR Plan", self.parent_plan):
            return
        start_date, end_date = get_plan_timeline(self.parent_plan)
        self.start_date = self.start_date or start_date
        self.end_date = self.end_date or end_date

    def validate_required_fields(self) -> None:
        required = {
            "objective_title": _("Objective Title"),
            "parent_plan": _("Plan"),
            "level": _("Level"),
            "priority": _("Priority"),
            "company": _("Organization"),
            "owner_user": _("Objective Owner"),
            "status": _("Status"),
        }
        for fieldname, label in required.items():
            if not self.get(fieldname):
                frappe.throw(_("{0} is required.").format(label))

        if self.level in {"Department", "Individual"} and not self.level_details:
            frappe.throw(_("Level Details is required for {0} level.").format(self.level))
        expected = {"Department": "Department", "Individual": "User"}.get(self.level)
        if expected and not frappe.db.exists(expected, self.level_details):
            frappe.throw(_("Level Details does not exist."))
        self.validate_team_assignments()

    def validate_team_assignments(self) -> None:
        if self.level != "Team":
            return

        teams = [row.team for row in self.teams]
        if not teams:
            frappe.throw(_("At least one User is required."))
        if any(not team for team in teams):
            frappe.throw(_("User rows cannot be empty."))
        if len(teams) != len(set(teams)):
            frappe.throw(_("Duplicate Users are not allowed."))

        missing = [team for team in teams if not frappe.db.exists("User", team)]
        if missing:
            frappe.throw(_("User {0} does not exist.").format(missing[0]))

    def validate_parent_relationships(self) -> None:
        if not frappe.db.exists("OKR Plan", self.parent_plan):
            frappe.throw(_("Selected Plan does not exist."))

        if self.exists_in_database() and self.has_value_changed("parent_plan"):
            frappe.throw(_("Objective cannot be moved between Plans."))

    def validate_lifecycle_transition(self) -> None:
        old_status = self.get_doc_before_save().status if not self.is_new() and self.get_doc_before_save() else None
        if not old_status or old_status == self.status:
            return

        allowed = STATUS_TRANSITIONS.get(old_status, set())
        if self.status not in allowed:
            frappe.throw(_("Invalid Objective status transition from {0} to {1}.").format(old_status, self.status))

        self.validate_transition_actor(old_status, self.status)

    def validate_transition_actor(self, old_status: str, new_status: str) -> None:
        roles = set(frappe.get_roles(frappe.session.user))
        if frappe.session.user == "Administrator" or roles.intersection(GOVERNANCE_ROLES):
            return

        user = frappe.session.user
        if new_status == "Completed" and user in {self.owner_user, self.plan_owner}:
            return
        if new_status in {"Active", "On Hold", "Closed"} and user == self.plan_owner:
            return

        frappe.throw(_("You are not allowed to change Objective status from {0} to {1}.").format(old_status, new_status))

    def validate_parent_status_dependencies(self) -> None:
        plan_status = frappe.db.get_value("OKR Plan", self.parent_plan, "status")
        if not plan_status:
            frappe.throw(_("Parent Plan status is required."))
        if plan_status == "Archived":
            frappe.throw(_("Objective cannot be created or updated under an Archived Plan."))
        if self.status in PLAN_ACTIVE_REQUIRED_STATUSES and plan_status != "Active":
            frappe.throw(_("Objective cannot become {0} unless Parent Plan is Active.").format(self.status))

    def validate_dates_inside_plan(self) -> None:
        start = getdate(self.start_date)
        end = getdate(self.end_date)
        if start > end:
            frappe.throw(_("Objective End Date cannot be before Start Date."))

        plan_start, plan_end = get_plan_timeline(self.parent_plan)
        if start < getdate(plan_start) or end > getdate(plan_end):
            frappe.throw(_("Objective dates must stay within the Plan period."))

    def validate_child_dates(self) -> None:
        if not self.name:
            return
        key_results = frappe.get_all(
            "OKR Key Result",
            filters={"objective": self.name},
            fields=["name", "end_date"],
        )
        outside = [
            row.name for row in key_results
            if row.end_date and not (getdate(self.start_date) <= getdate(row.end_date) <= getdate(self.end_date))
        ]
        if outside:
            frappe.throw(_("Objective timeline cannot exclude existing Key Result Target Dates."))

    def validate_duplicate_title_in_plan(self) -> None:
        duplicate = frappe.db.exists(
            "OKR Objective",
            {
                "name": ["!=", self.name],
                "parent_plan": self.parent_plan,
                "objective_title": self.objective_title,
            },
        )
        if duplicate:
            frappe.throw(_("An Objective with this title already exists in the selected Plan."))

    def validate_completion_criteria(self) -> None:
        if self.status != "Completed":
            return

        key_results = self.get_key_results()
        incomplete = [row for row in key_results if row.get("status") not in COMPLETED_KR_STATUSES]
        if key_results and not incomplete:
            return

        if not self.partial_completion_accepted:
            frappe.throw(_("Objective can be completed only when all Key Results are completed or a manager accepts partial completion."))

        if not self.is_manager_or_owner_accepting_completion():
            frappe.throw(_("Only a manager or Plan Owner can accept partial Objective completion."))

    def is_manager_or_owner_accepting_completion(self) -> bool:
        roles = set(frappe.get_roles(frappe.session.user))
        return (
            frappe.session.user == "Administrator"
            or bool(roles.intersection(MANAGER_ROLES))
            or frappe.session.user == self.plan_owner
        )

    def validate_locked_fields(self) -> None:
        if self.is_new():
            return
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return

        locked_fields = set()
        if old_doc.status in SETUP_LOCKED_STATUSES or self.has_key_results():
            locked_fields.update(SETUP_LOCKED_FIELDS)
        if old_doc.status in ACTIVE_LOCKED_STATUSES:
            locked_fields.update(ACTIVE_LOCKED_FIELDS)
        if old_doc.status in {"Closed"}:
            locked_fields.update({"priority", "reviewer", "description", "partial_completion_accepted", "completion_notes"})

        for fieldname in locked_fields:
            if self.has_value_changed(fieldname):
                frappe.throw(_("{0} cannot be changed in the current Objective lifecycle.").format(self.meta.get_label(fieldname)))

    def validate_system_fields(self) -> None:
        for fieldname, value in self.get_system_summary_values().items():
            setattr(self, fieldname, value)

    def get_key_results(self) -> list[dict[str, Any]]:
        if not self.name:
            return []
        progress_field = "target_progress" if frappe.get_meta("OKR Key Result").has_field("target_progress") else "progress"
        return frappe.get_all(
            "OKR Key Result",
            filters={"objective": self.name},
            fields=["name", "status", progress_field],
        )

    def has_key_results(self) -> bool:
        return bool(self.name and frappe.db.exists("OKR Key Result", {"objective": self.name}))

    def get_system_summary_values(self) -> dict[str, Any]:
        key_results = self.get_key_results()
        progress_field = "target_progress" if frappe.get_meta("OKR Key Result").has_field("target_progress") else "progress"
        progress_values = [row.get(progress_field) for row in key_results]
        progress = round(sum(flt(value) for value in progress_values) / len(progress_values), 2) if progress_values else 0.0
        return {"progress": progress, "key_result_count": len(key_results)}

    def update_system_summary_fields(self) -> None:
        for fieldname, value in self.get_system_summary_values().items():
            setattr(self, fieldname, value)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_team_options(doctype, txt, searchfield, start, page_len, filters):
    users = frappe.get_all(
        "User",
        filters={"enabled": 1},
        or_filters={
            "name": ["like", f"%{txt}%"],
            "full_name": ["like", f"%{txt}%"],
        },
        fields=["name", "full_name"],
        order_by="full_name asc",
        start=start,
        page_length=page_len,
    )
    return [(user.name, user.full_name or user.name) for user in users]
