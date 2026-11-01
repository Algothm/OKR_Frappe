from unittest import TestCase
from unittest.mock import patch

import frappe

from okr_management.permissions import has_group_permission, get_group_permission_query_conditions
from okr_management.okr_management.doctype.okr_objective.okr_objective import OKRObjective


class TestGroupRequirements(TestCase):
    def test_missing_group_rejected_even_with_department(self):
        for department in (None, "Department"):
            objective = frappe._dict(group=None, department=department)
            with patch("okr_management.okr_management.doctype.okr_objective.okr_objective._", side_effect=lambda value: value), patch("frappe.throw", side_effect=frappe.ValidationError("Group is required")):
                with self.assertRaises(frappe.ValidationError):
                    OKRObjective.sync_group_context(objective)

    def test_okr_user_group_permissions(self):
        with patch("okr_management.permissions.frappe.get_roles", return_value=["OKR User"]):
            for permission in ("read", "select", "create"):
                self.assertTrue(has_group_permission(ptype=permission, user="user@example.com"))
            for permission in ("write", "delete", "share"):
                self.assertFalse(has_group_permission(ptype=permission, user="user@example.com"))
            self.assertEqual(get_group_permission_query_conditions("user@example.com"), "")

    def test_admin_roles_can_manage_groups(self):
        for role in ("OKR Admin", "System Manager"):
            with patch("okr_management.permissions.frappe.get_roles", return_value=[role]):
                for permission in ("create", "read", "write", "delete"):
                    self.assertTrue(has_group_permission(ptype=permission, user="admin@example.com"))

    def test_other_roles_cannot_create_groups(self):
        with patch("okr_management.permissions.frappe.get_roles", return_value=["Employee"]):
            self.assertFalse(has_group_permission(ptype="create", user="user@example.com"))
