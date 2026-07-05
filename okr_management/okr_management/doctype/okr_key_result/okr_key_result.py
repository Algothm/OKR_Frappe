from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


VALID_PRIORITIES = {"Low", "Medium", "High"}
VALID_STATUSES = {"Draft", "Planned", "Active", "On Hold", "Completed", "Closed", "Archived"}
VALID_CALCULATION_MODES = {"Manual", "Automatic"}
VALID_MEASUREMENT_TYPES = {"Percentage", "Number", "Currency", "Boolean"}
VALID_MEASUREMENT_DIRECTIONS = {"Increase", "Decrease"}

INHERITED_FIELDS = {
    "parent_plan",
    "parent_sprint",
    "objective_title",
    "company",
    "financial_year",
    "department",
    "plan_owner",
    "sprint_owner",
    "objective_owner",
    "objective_level",
    "start_date",
    "end_date",
}

# Placeholder values mapping removed


class OKRKeyResult(Document):
    def sync_action_items_to_db(self) -> None:
        import os
        with open("/tmp/kr_save.log", "a") as lf:
            lf.write(f"sync_action_items_to_db called for {self.name}\n")
            for row in self.get("action_items") or []:
                lf.write(f"  Row id: {row.action_item_id}, title: {row.action_item_title}, progress: {row.progress}\n")
        for row in self.get("action_items") or []:
            if row.action_item_id and frappe.db.exists("OKR Action Item", row.action_item_id):
                ai = frappe.get_doc("OKR Action Item", row.action_item_id)
                updated = False
                if ai.progress != row.progress:
                    ai.progress = row.progress
                    updated = True
                if ai.status != row.status:
                    ai.status = row.status
                    updated = True
                if ai.priority != row.priority:
                    ai.priority = row.priority
                    updated = True
                if updated:
                    ai.flags.ignore_permissions = True
                    ai.save()

    def before_validate(self) -> None:
        self.priority = self.priority or "Medium"
        self.status = self.status or "Draft"
        self.calculation_mode = self.calculation_mode or "Manual"
        self.metric_type = self.metric_type or "Percentage"
        self.metric_direction = self.metric_direction or "Increase"
        
        if self.baseline_value is None:
            self.baseline_value = 0.0
            
        if self.current_value is None:
            self.current_value = 0.0
            
        if self.is_new() and self.metric_type == "Percentage" and self.target_value is None:
            self.target_value = 100.0
        elif self.metric_type == "Boolean" and self.target_value not in [0.0, 1.0]:
            self.target_value = 1.0
            
        if self.metric_type == "Percentage" and not self.unit_of_measure:
            self.unit_of_measure = "%"
        elif self.metric_type in ["Boolean", "Currency"]:
            self.unit_of_measure = None

        self.inherit_context_from_objective()
        self.sync_action_items_to_db()
        
        # Calculate count of standalone Action Items and check-ins
        if self.name:
            self.action_item_count = frappe.db.count("OKR Action Item", {"parent_key_result": self.name})
            self.checkin_count = frappe.db.count("OKR Check In", {"key_result": self.name})
            
            from okr_management.utils.okr_calculations import get_key_result_progress
            self.target_progress = get_key_result_progress(self.name, self)
            self.score = self.target_progress
        else:
            self.action_item_count = 0
            self.checkin_count = 0
            self.target_progress = 0.0
            self.score = 0.0

        self.sync_action_item_parent()

    def validate(self) -> None:
        self.inherit_context_from_objective()
        self.validate_required_fields()
        self.validate_options()
        self.validate_measurement()
        self.validate_inherited_fields_locked()

    def inherit_context_from_objective(self) -> None:
        if not self.objective:
            self.clear_inherited_context()
            return

        if not frappe.db.exists("OKR Objective", self.objective):
            return

        objective = frappe.db.get_value(
            "OKR Objective",
            self.objective,
            [
                "parent_plan",
                "sprint",
                "objective_title",
                "company",
                "financial_year",
                "department",
                "plan_owner",
                "sprint_owner",
                "owner_user",
                "level",
                "start_date",
                "end_date",
            ],
            as_dict=True,
        )
        if not objective:
            self.clear_inherited_context()
            return

        self.parent_plan = objective.parent_plan
        self.parent_sprint = objective.sprint
        self.objective_title = objective.objective_title
        self.company = objective.company
        self.financial_year = objective.financial_year
        self.department = objective.department
        self.plan_owner = objective.plan_owner
        self.sprint_owner = objective.sprint_owner
        self.objective_owner = objective.owner_user
        self.objective_level = objective.level
        self.start_date = objective.start_date
        self.end_date = objective.end_date

    def clear_inherited_context(self) -> None:
        for fieldname in INHERITED_FIELDS:
            setattr(self, fieldname, None)

    # Placeholder setter removed

    def sync_action_item_parent(self) -> None:
        for action_item in self.get("action_items") or []:
            action_item.parent_key_result = self.name

    def validate_required_fields(self) -> None:
        required = {
            "key_result_title": _("Key Result Title"),
            "objective": _("Parent Objective"),
            "owner_user": _("Key Result Owner"),
            "priority": _("Priority"),
            "status": _("Status"),
            "calculation_mode": _("Calculation Mode"),
            "metric_type": _("Measurement Type"),
            "metric_direction": _("Measurement Direction"),
        }
        for fieldname, label in required.items():
            if not self.get(fieldname):
                frappe.throw(_("{0} is required.").format(label))

        if not frappe.db.exists("OKR Objective", self.objective):
            frappe.throw(_("Parent Objective does not exist."))

    def validate_options(self) -> None:
        if self.priority not in VALID_PRIORITIES:
            frappe.throw(_("Priority must be Low, Medium, or High."))
        if self.status not in VALID_STATUSES:
            frappe.throw(_("Status must be Draft, Planned, Active, On Hold, Completed, Closed, or Archived."))
        if self.calculation_mode not in VALID_CALCULATION_MODES:
            frappe.throw(_("Calculation Mode must be Manual or Automatic."))
        if self.metric_type not in VALID_MEASUREMENT_TYPES:
            frappe.throw(_("Measurement Type must be Percentage, Number, Currency, or Boolean."))
        if self.metric_direction not in VALID_MEASUREMENT_DIRECTIONS:
            frappe.throw(_("Measurement Direction must be Increase or Decrease."))

    def validate_measurement(self) -> None:
        if self.metric_type != "Currency":
            self.currency = None

        if self.metric_type in ["Percentage", "Boolean"] and self.target_value is None:
            frappe.throw(_("Target Value is required for Measurement Type {0}.").format(self.metric_type))

        if self.calculation_mode == "Automatic" and self.get_doc_before_save():
            if self.has_value_changed("current_value"):
                frappe.throw(_("Current Value is editable only when Calculation Mode is Manual."))

        if self.calculation_mode == "Automatic" and self.is_new() and self.current_value:
            frappe.throw(_("Current Value is editable only when Calculation Mode is Manual."))

    def validate_inherited_fields_locked(self) -> None:
        if self.is_new():
            return

        previous = self.get_doc_before_save()
        if not previous:
            return

        if self.has_value_changed("objective"):
            return

        for fieldname in INHERITED_FIELDS:
            if self.has_value_changed(fieldname):
                frappe.throw(_("{0} is inherited from Parent Objective and cannot be changed manually.").format(self.meta.get_label(fieldname)))

    # Placeholder validation removed
