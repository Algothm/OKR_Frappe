from __future__ import annotations

import inspect
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from okr_management.utils.okr_calculations import recalculate_key_result_progress
from okr_management.utils.okr_validations import ensure_percentage, ensure_required_link

STATUS_TRANSITIONS = {
    "Draft": {"Planned", "Cancelled"},
    "Planned": {"In Progress", "Blocked", "Cancelled"},
    "In Progress": {"Blocked", "Completed", "Cancelled"},
    "Blocked": {"In Progress", "Cancelled"},
    "Completed": {"In Progress", "Closed"},
    "Cancelled": {"Draft"},
    "Closed": {"Archived"},
    "Archived": set(),
}


def get_parent_doc_from_stack(child_doc):
    for frame_info in inspect.stack():
        frame = frame_info.frame
        for var_val in frame.f_locals.values():
            if var_val and hasattr(var_val, "doctype") and getattr(var_val, "doctype") == "OKR Key Result":
                action_items = var_val.get("action_items") or []
                if child_doc in action_items or any(item.name == child_doc.name for item in action_items if item.name and child_doc.name):
                    return var_val
    return None


class OKRActionItem(Document):
    def before_validate(self) -> None:
        self.status = self.status or "Draft"
        self.progress = flt(self.progress)
        self.weight = flt(self.weight)
        self.owner_user = self.owner_user or frappe.session.user
        self.inherit_context_from_key_result()
        self.default_dates_from_key_result()

    def validate(self) -> None:
        self.before_validate()
        if self.parenttype == "OKR Key Result" and self.parent:
            self.parent_key_result = self.parent
        ensure_required_link(self.action_item_title, "Action Item Title")
        ensure_required_link(self.owner_user, "Action Item Owner")
        ensure_required_link(self.status, "Status")
        ensure_percentage(self.weight, "Weight %")
        ensure_percentage(self.progress, "Progress %")
        self.validate_parent_context()
        self.validate_dates()
        self.validate_lifecycle()
        self.validate_weight_sum()

    def on_update(self) -> None:
        parent = getattr(self, "parent_key_result", None) or getattr(self, "parent", None)
        if parent and frappe.db.exists("OKR Key Result", parent):
            recalculate_key_result_progress(parent)

    def before_delete(self) -> None:
        self.validate_delete_allowed()

    def on_trash(self) -> None:
        self.validate_delete_allowed()
        parent = getattr(self, "parent_key_result", None) or getattr(self, "parent", None)
        if parent and frappe.db.exists("OKR Key Result", parent):
            recalculate_key_result_progress(parent)

    def inherit_context_from_key_result(self) -> None:
        parent_kr = get_parent_doc_from_stack(self)
        parent = getattr(self, "parent_key_result", None) or getattr(self, "parent", None)
        if not parent_kr and parent and frappe.db.exists("OKR Key Result", parent):
            parent_kr = frappe.get_doc("OKR Key Result", parent)
        if parent_kr:
            self.parent_key_result = parent_kr.name or parent
            self.parent_objective = parent_kr.objective
            self.parent_sprint = parent_kr.parent_sprint
            self.parent_plan = parent_kr.parent_plan
            self.company = parent_kr.company
            self.department = parent_kr.department

    def default_dates_from_key_result(self) -> None:
        parent_kr = get_parent_doc_from_stack(self)
        parent = getattr(self, "parent_key_result", None) or getattr(self, "parent", None)
        if not parent_kr and parent and frappe.db.exists("OKR Key Result", parent):
            parent_kr = frappe.get_doc("OKR Key Result", parent)
        if parent_kr:
            if not self.start_date:
                self.start_date = parent_kr.start_date
            if not self.due_date:
                self.due_date = parent_kr.end_date

    def validate_parent_context(self) -> None:
        parent_kr = get_parent_doc_from_stack(self)
        parent = getattr(self, "parent_key_result", None) or getattr(self, "parent", None)
        if not parent_kr:
            if not parent:
                frappe.throw(_("Parent Key Result is required."))
            if not frappe.db.exists("OKR Key Result", parent):
                frappe.throw(_("Parent Key Result does not exist."))
            parent_kr = frappe.get_doc("OKR Key Result", parent)
        
        # Check if parent KR is Closed or Archived
        if parent_kr.status in ("Closed", "Archived"):
            frappe.throw(_("Cannot create or update Action Items under a Closed or Archived Key Result."))
            
        # Check parent KR Active dependency when transitioning to In Progress
        if self.status == "In Progress" and parent_kr.status != "Active":
            frappe.throw(_("Action Item cannot transition to In Progress unless Parent Key Result is Active."))

    def validate_dates(self) -> None:
        parent_kr = get_parent_doc_from_stack(self)
        parent = getattr(self, "parent_key_result", None) or getattr(self, "parent", None)
        if not parent_kr:
            if not parent or not frappe.db.exists("OKR Key Result", parent):
                return
            parent_kr = frappe.get_doc("OKR Key Result", parent)
        if not parent_kr.start_date or not parent_kr.end_date:
            return
            
        start = getdate(self.start_date)
        due = getdate(self.due_date)
        if start > due:
            frappe.throw(_("Start Date cannot be after Due Date."))
            
        parent_start = getdate(parent_kr.start_date)
        parent_end = getdate(parent_kr.end_date)
        if start < parent_start or due > parent_end:
            frappe.throw(_("Action Item dates must fall within Parent Key Result dates ({0} to {1}).").format(parent_kr.start_date, parent_kr.end_date))

    def validate_lifecycle(self) -> None:
        # Check previous status
        if self.name and frappe.db.exists("OKR Action Item", self.name):
            prev = frappe.db.get_value("OKR Action Item", self.name, ["status", "completion_date"], as_dict=True)
            previous_status = prev.status
            previous_completion_date = prev.completion_date
        else:
            previous_status = None
            previous_completion_date = None

        if not previous_status:
            if self.status != "Draft":
                frappe.throw(_("New Action Items must start in Draft status."))
        elif previous_status != self.status:
            if self.status not in STATUS_TRANSITIONS.get(previous_status, set()):
                frappe.throw(_("Invalid Action Item status transition from {0} to {1}.").format(previous_status, self.status))

        # Handle completion_date
        if self.status == "Completed":
            if not self.completion_date:
                self.completion_date = today()
        
        # Handle immutability of completion_date unless changed by authorized Manager/Admin
        if previous_completion_date and self.completion_date and getdate(self.completion_date) != getdate(previous_completion_date):
            roles = set(frappe.get_roles(frappe.session.user))
            is_manager_or_admin = (
                "System Manager" in roles
                or "Administrator" in roles
                or "OKR Admin" in roles
                or "OKR Manager" in roles
                or frappe.session.user == "Administrator"
            )
            if not is_manager_or_admin:
                frappe.throw(_("Only an authorized Manager or Admin can reset the Completion Date."))

    def validate_weight_sum(self) -> None:
        parent = getattr(self, "parent_key_result", None) or getattr(self, "parent", None)
        if not parent:
            return
            
        parent_kr = get_parent_doc_from_stack(self)
        if parent_kr:
            all_rows = parent_kr.get("action_items") or []
        else:
            siblings = frappe.get_all(
                "OKR Action Item",
                filters={"parenttype": "OKR Key Result", "parent": parent},
                fields=["name", "status", "weight"]
            )
            sibling_map = {s.name: s for s in siblings}
            if self.name:
                sibling_map[self.name] = self
            else:
                sibling_map["__current_new_row"] = self
            all_rows = list(sibling_map.values())

        active_siblings = [r for r in all_rows if r.status != "Cancelled"]
        
        if len(active_siblings) > 1 and any(flt(r.weight) > 0 for r in active_siblings):
            total_weight = sum(flt(r.weight) for r in active_siblings)
            if round(total_weight, 2) != 100.00:
                frappe.throw(_("The sum of weights of all non-cancelled Action Items must equal exactly 100% (currently {0}%).").format(total_weight))

    def validate_delete_allowed(self) -> None:
        if self.status != "Draft":
            frappe.throw(_("Cannot delete Action Item unless its status is Draft (current status: {0}).").format(self.status))

    def _get_missing_mandatory_fields(self):
        self.validate()
        return super()._get_missing_mandatory_fields()
