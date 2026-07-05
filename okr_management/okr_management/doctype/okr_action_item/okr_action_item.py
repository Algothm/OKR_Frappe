from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link


class OKRActionItem(Document):
    def before_validate(self) -> None:
        self.status = self.status or "Open"
        self.priority = self.priority or "Medium"
        self.progress = flt(self.progress or 0.0)
        self.owner_user = self.owner_user or frappe.session.user

        # Default Action Date (due_date) to today on creation
        if self.is_new() and not self.due_date:
            self.due_date = today()

        self.set_parent_key_result_from_child_context()
        self.inherit_context_from_key_result()

    def validate(self) -> None:
        ensure_required_link(self.action_item_title, "Action Item Title")
        ensure_required_link(self.parent_key_result, "Parent Key Result")
        ensure_required_link(self.owner_user, "Action Item Owner")
        ensure_required_link(self.status, "Status")
        ensure_percentage(self.progress, "Progress %")
        self.validate_parent_context()
        self.validate_lifecycle()

    def on_update(self) -> None:
        self.update_parent_action_item_count()
        if self.parent_key_result:
            from okr_management.utils.okr_calculations import recalculate_key_result_progress
            recalculate_key_result_progress(self.parent_key_result)

    def on_trash(self) -> None:
        self.update_parent_action_item_count(delta=-1)

    def after_delete(self) -> None:
        if self.parent_key_result:
            from okr_management.utils.okr_calculations import recalculate_key_result_progress
            recalculate_key_result_progress(self.parent_key_result)

    def set_parent_key_result_from_child_context(self) -> None:
        if self.parent_key_result:
            return

        if self.parenttype == "OKR Key Result" and self.parent:
            self.parent_key_result = self.parent
        elif self.parenttype == "OKR Check In" and self.parent:
            self.parent_key_result = frappe.db.get_value("OKR Check In", self.parent, "key_result")

    def inherit_context_from_key_result(self) -> None:
        if self.parent_key_result and frappe.db.exists("OKR Key Result", self.parent_key_result):
            parent_kr = frappe.get_doc("OKR Key Result", self.parent_key_result)
            self.parent_objective = parent_kr.objective
            self.parent_sprint = parent_kr.parent_sprint
            self.parent_plan = parent_kr.parent_plan
            self.company = parent_kr.company
            self.department = parent_kr.department
            self.financial_year = parent_kr.financial_year
            if not self.reviewer:
                self.reviewer = parent_kr.reviewer

    def validate_parent_context(self) -> None:
        if not self.parent_key_result:
            frappe.throw(_("Parent Key Result is required."))
        if not frappe.db.exists("OKR Key Result", self.parent_key_result):
            frappe.throw(_("Parent Key Result does not exist."))

    def validate_lifecycle(self) -> None:
        # Handle completion_date
        if self.status == "Completed":
            if not self.completion_date:
                self.completion_date = today()
        else:
            self.completion_date = None

    def update_parent_action_item_count(self, delta: int = 0) -> None:
        if not self.parent_key_result or not frappe.db.exists("OKR Key Result", self.parent_key_result):
            return

        count = frappe.db.count("OKR Action Item", {"parent_key_result": self.parent_key_result}) + delta
        frappe.db.set_value("OKR Key Result", self.parent_key_result, "action_item_count", max(count, 0), update_modified=False)
