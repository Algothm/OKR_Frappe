from __future__ import annotations

import frappe

from okr_management.permissions import is_okr_admin


EDITABLE_PLAN_TEAM_ROLES = {"Admin", "Contributor"}


def _plan_team_plans(user, roles=None):
    filters = {"member_user": user, "parenttype": "OKR Plan"}
    if roles:
        filters["role"] = ["in", sorted(roles)]
    return set(frappe.get_all("OKR Plan Team Member", filters=filters, pluck="parent"))


def get_hierarchy_visibility_scope(user=None):
    user = user or frappe.session.user
    admin_user = is_okr_admin(user)
    if admin_user:
        return {
            "visible_objectives": set(),
            "visible_key_results": set(),
            "visible_action_items": set(),
            "owned_objectives": set(),
            "owned_key_results": set(),
            "full_key_results": set(),
            "direct_action_items": set(),
            "full_plan_names": set(),
            "editable_plan_names": set(),
            "checkin_override": False,
            "read_all": True,
        }

    employee_rows = frappe.get_all(
        "Employee",
        filters={"user_id": user, "status": "Active"},
        fields=["name", "department"],
    )
    employees = {row.name for row in employee_rows}
    user_departments = {row.department for row in employee_rows if row.department}
    full_plan_names = _plan_team_plans(user)
    editable_plan_names = _plan_team_plans(user, EDITABLE_PLAN_TEAM_ROLES)
    department_objectives = set()
    if user_departments and "Department Head" in frappe.get_roles(user):
        department_objectives.update(
            frappe.get_all(
                "OKR Objective",
                filters={"department": ["in", list(user_departments)]},
                pluck="name",
            )
        )
    owned_objectives = set(frappe.get_all("OKR Objective", filters={"owner_user": user}, pluck="name"))
    owned_objectives.update(frappe.get_all("OKR Objective", filters={"owner": user}, pluck="name"))
    owned_krs = set(frappe.get_all("OKR Key Result", filters={"assignee": user}, pluck="name"))
    owned_krs.update(frappe.get_all("OKR Key Result", filters={"owner_user": user}, pluck="name"))

    authority_objectives = owned_objectives | department_objectives
    authority_krs = set(owned_krs)
    if authority_objectives:
        authority_krs.update(
            frappe.get_all("OKR Key Result", filters={"objective": ["in", list(authority_objectives)]}, pluck="name")
        )

    direct_actions = set()
    if employees:
        direct_actions.update(
            frappe.get_all("OKR Action Item", filters={"assigned_to": ["in", list(employees)]}, pluck="name")
        )

    actions = set(direct_actions)
    if authority_krs:
        actions.update(
            frappe.get_all("OKR Action Item", filters={"parent_key_result": ["in", list(authority_krs)]}, pluck="name")
        )

    krs = set(authority_krs)
    if direct_actions:
        krs.update(
            filter(
                None,
                frappe.get_all(
                    "OKR Action Item",
                    filters={"name": ["in", list(direct_actions)]},
                    pluck="parent_key_result",
                ),
            )
        )

    objectives = set(authority_objectives)
    if krs:
        objectives.update(
            filter(
                None,
                frappe.get_all(
                    "OKR Key Result",
                    filters={"name": ["in", list(krs)]},
                    pluck="objective",
                ),
            )
        )

    return {
        "visible_objectives": objectives,
        "visible_key_results": krs,
        "visible_action_items": actions,
        "owned_objectives": owned_objectives,
        "owned_key_results": owned_krs,
        "full_key_results": authority_krs,
        "direct_action_items": direct_actions,
        "full_plan_names": full_plan_names,
        "editable_plan_names": editable_plan_names,
        "checkin_override": False,
        "read_all": False,
    }


def _condition(doctype, names):
    if not names:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(name) for name in sorted(names))
    return f"`tab{doctype}`.name in ({escaped})"


def _query(scope_key, doctype, user=None):
    scope = get_hierarchy_visibility_scope(user)
    return "" if scope["read_all"] else _condition(doctype, scope[scope_key])


def objective_query(user=None):
    return _query("visible_objectives", "OKR Objective", user)


def key_result_query(user=None):
    return _query("visible_key_results", "OKR Key Result", user)


def action_item_query(user=None):
    return _query("visible_action_items", "OKR Action Item", user)


def checkin_query(user=None):
    scope = get_hierarchy_visibility_scope(user)
    if scope["read_all"]:
        return ""
    names = scope["visible_action_items"]
    if not names:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(name) for name in sorted(names))
    return f"`tabOKR Check In`.action_item in ({escaped})"


def _hierarchy_permission(doc, user, ptype, read_key, write_key):
    scope = get_hierarchy_visibility_scope(user)
    if scope["read_all"]:
        return None
    if ptype in {"write", "delete", "submit", "cancel", "amend"}:
        return doc.name in scope[write_key]
    return doc.name in scope[read_key]


def objective_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    scope = get_hierarchy_visibility_scope(user)
    if ptype == "create" and not scope["read_all"]:
        return user not in {"Guest", ""}
    return _hierarchy_permission(doc, user, ptype, "visible_objectives", "owned_objectives")


def key_result_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    scope = get_hierarchy_visibility_scope(user)
    if ptype == "create" and not scope["read_all"]:
        return bool(doc.objective) and (
            doc.objective in scope["owned_objectives"]
            or frappe.db.get_value("OKR Objective", doc.objective, "parent_plan") in scope["editable_plan_names"]
        )
    return _hierarchy_permission(doc, user, ptype, "visible_key_results", "owned_key_results")


def action_item_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    scope = get_hierarchy_visibility_scope(user)
    if ptype == "create" and not scope["read_all"]:
        if not doc.parent_key_result:
            return False
        parent = frappe.db.get_value(
            "OKR Key Result", doc.parent_key_result, ["objective", "parent_plan"], as_dict=True
        )
        return bool(parent) and (
            doc.parent_key_result in scope["owned_key_results"]
            or parent.objective in scope["owned_objectives"]
            or parent.parent_plan in scope["editable_plan_names"]
        )
    return _hierarchy_permission(doc, user, ptype, "visible_action_items", "direct_action_items")


def checkin_permission(doc, user=None, ptype=None):
    user = user or frappe.session.user
    scope = get_hierarchy_visibility_scope(user)
    # Frappe checks ``write`` on a blank, unsaved document before uploading an
    # attachment. The Action Item is not present on that temporary document,
    # so defer to the DocType's role permissions for this one upload check.
    # Normal create/validate checks still require an Action Item assigned to
    # the logged-in employee before the Check-In can be inserted.
    if ptype == "write" and doc.is_new():
        return user not in {"Guest", ""} and bool(
            frappe.db.exists("Employee", {"user_id": user, "status": "Active"})
        )
    if ptype in {"create", "write", "delete", "submit", "cancel", "amend"}:
        return bool(doc.action_item) and doc.action_item in scope["direct_action_items"]
    if scope["read_all"]:
        return None
    return doc.action_item in scope["visible_action_items"]
