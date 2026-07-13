from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from okr_management.utils.okr_calculations import recalculate_objective_progress, recalculate_sprint_progress


STATUS_TRANSITIONS = {
    "Draft": {"Active"},
    "Active": {"On Hold", "Completed"},
    "On Hold": {"Active", "Completed"},
    "Completed": {"Closed"},
    "Closed": set(),
}

SETUP_LOCKED_STATUSES = {"Active", "On Hold", "Completed", "Closed"}
ACTIVE_LOCKED_STATUSES = {"Active", "On Hold", "Completed", "Closed"}
PLAN_ACTIVE_REQUIRED_STATUSES = {"Active", "On Hold"}
SPRINT_ACTIVE_REQUIRED_STATUSES = {"Active", "On Hold"}
COMPLETED_KR_STATUSES = {"Achieved", "Completed", "Closed"}
GOVERNANCE_ROLES = {"OKR Admin", "OKR Manager"}
MANAGER_ROLES = {"OKR Admin", "OKR Manager", "Department Head"}

SETUP_LOCKED_FIELDS = {
    "parent_plan",
    "sprint",
    "financial_year",
    "company",
    "department",
    "plan_owner",
    "sprint_owner",
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
        self.owner_user = self.owner_user or frappe.session.user
        self.inherit_context_from_sprint()
        self.default_dates_from_sprint()
        self.update_system_summary_fields()

    def validate(self) -> None:
        self.validate_required_fields()
        self.validate_parent_relationships()
        self.validate_lifecycle_transition()
        self.validate_parent_status_dependencies()
        self.validate_dates_inside_sprint()
        self.validate_duplicate_title_in_sprint()
        self.validate_completion_criteria()
        self.validate_locked_fields()
        self.validate_system_fields()

    def on_update(self) -> None:
        values = self.get_system_summary_values()
        if values:
            frappe.db.set_value(self.doctype, self.name, values, update_modified=False)
        recalculate_sprint_progress(self.sprint)

    def on_trash(self) -> None:
        if self.has_key_results():
            frappe.throw(_("Cannot delete Objective because Key Results exist."))

    def exists_in_database(self) -> bool:
        return bool(self.name and frappe.db.exists(self.doctype, self.name))

    def inherit_context_from_sprint(self) -> None:
        if not self.sprint or not frappe.db.exists("OKR Sprint", self.sprint):
            return

        sprint = frappe.db.get_value(
            "OKR Sprint",
            self.sprint,
            [
                "parent_plan",
                "financial_year",
                "company",
                "department",
                "plan_owner",
                "sprint_owner",
                "start_date",
                "end_date",
                "status",
            ],
            as_dict=True,
        )
        if not sprint:
            return

        self.parent_plan = sprint.parent_plan
        self.financial_year = sprint.financial_year
        self.company = sprint.company
        self.plan_owner = sprint.plan_owner
        self.sprint_owner = sprint.sprint_owner

    def default_dates_from_sprint(self) -> None:
        if not self.sprint or not frappe.db.exists("OKR Sprint", self.sprint):
            return
        sprint_dates = frappe.db.get_value("OKR Sprint", self.sprint, ["start_date", "end_date"], as_dict=True)
        if not sprint_dates:
            return
        if not self.start_date:
            self.start_date = sprint_dates.start_date
        if not self.end_date:
            self.end_date = sprint_dates.end_date

    def validate_required_fields(self) -> None:
        required = {
            "objective_title": _("Objective Title"),
            "sprint": _("Sprint"),
            "parent_plan": _("Parent Plan"),
            "priority": _("Priority"),
            "company": _("Organization"),
            "owner_user": _("Objective Owner"),
            "start_date": _("Start Date"),
            "end_date": _("End Date"),
            "status": _("Status"),
        }
        for fieldname, label in required.items():
            if not self.get(fieldname):
                frappe.throw(_("{0} is required.").format(label))

        if not self.department:
            frappe.throw(_("Department is required."))

    def validate_parent_relationships(self) -> None:
        if not frappe.db.exists("OKR Sprint", self.sprint):
            frappe.throw(_("Sprint does not exist."))

        sprint_plan = frappe.db.get_value("OKR Sprint", self.sprint, "parent_plan")
        if not sprint_plan:
            frappe.throw(_("Sprint must belong to an OKR Plan."))
        if self.parent_plan != sprint_plan:
            frappe.throw(_("Parent Plan must match the selected Sprint's Parent Plan."))

        if not frappe.db.exists("OKR Plan", self.parent_plan):
            frappe.throw(_("Parent Plan does not exist."))

        if self.exists_in_database() and self.has_key_results() and self.has_value_changed("sprint"):
            frappe.throw(_("Cannot move Objective to another Sprint after Key Results exist."))

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
        if new_status == "Completed" and user in {self.owner_user, self.sprint_owner}:
            return
        if new_status in {"Active", "On Hold", "Closed"} and user in {self.sprint_owner, self.plan_owner}:
            return

        frappe.throw(_("You are not allowed to change Objective status from {0} to {1}.").format(old_status, new_status))

    def validate_parent_status_dependencies(self) -> None:
        sprint_status, plan_status = frappe.db.get_value(
            "OKR Sprint", self.sprint, ["status", "parent_plan"], as_dict=False
        ) or (None, None)
        if not sprint_status:
            frappe.throw(_("Sprint status is required."))

        if sprint_status in {"Closed", "Archived"}:
            frappe.throw(_("Objective cannot be created or updated under a Closed or Archived Sprint."))

        actual_plan_status = frappe.db.get_value("OKR Plan", self.parent_plan, "status")
        if self.status in PLAN_ACTIVE_REQUIRED_STATUSES and actual_plan_status != "Active":
            frappe.throw(_("Objective cannot become {0} unless Parent Plan is Active.").format(self.status))

        if self.status in SPRINT_ACTIVE_REQUIRED_STATUSES and sprint_status != "Active":
            frappe.throw(_("Objective cannot become {0} unless Sprint is Active.").format(self.status))

    def validate_dates_inside_sprint(self) -> None:
        start = getdate(self.start_date)
        end = getdate(self.end_date)
        if start > end:
            frappe.throw(_("Objective End Date cannot be before Start Date."))

        sprint_dates = frappe.db.get_value("OKR Sprint", self.sprint, ["start_date", "end_date"], as_dict=True)
        if not sprint_dates or not sprint_dates.start_date or not sprint_dates.end_date:
            frappe.throw(_("Sprint must have Start Date and End Date."))

        sprint_start = getdate(sprint_dates.start_date)
        sprint_end = getdate(sprint_dates.end_date)
        if start < sprint_start or end > sprint_end:
            frappe.throw(_("Objective dates must stay within the Sprint date range."))

    def validate_duplicate_title_in_sprint(self) -> None:
        duplicate = frappe.db.exists(
            "OKR Objective",
            {
                "name": ["!=", self.name],
                "sprint": self.sprint,
                "objective_title": self.objective_title,
            },
        )
        if duplicate:
            frappe.throw(_("An Objective with this title already exists in the selected Sprint."))

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
            frappe.throw(_("Only a manager, Plan Owner, or Sprint Owner can accept partial Objective completion."))

    def is_manager_or_owner_accepting_completion(self) -> bool:
        roles = set(frappe.get_roles(frappe.session.user))
        return (
            frappe.session.user == "Administrator"
            or bool(roles.intersection(MANAGER_ROLES))
            or frappe.session.user in {self.plan_owner, self.sprint_owner}
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
