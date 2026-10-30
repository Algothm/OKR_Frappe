import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import frappe

from okr_management.permissions import is_okr_admin
from okr_management.okr_management.doctype.okr_check_in.okr_check_in import OKRCheckIn


class TestCheckInDeletePermissions(TestCase):
    def test_either_admin_role_allows_deletion_in_any_status(self):
        for role in ("OKR Admin", "System Manager"):
            with patch("okr_management.permissions.frappe.get_roles", return_value=[role]):
                with patch("okr_management.okr_management.doctype.okr_check_in.okr_check_in.is_okr_admin", side_effect=lambda: is_okr_admin("admin@example.com")):
                    for status in ("Draft", "In Progress", "Submitted"):
                        OKRCheckIn.on_trash(frappe._dict(status=status))

    def test_regular_user_cannot_delete_in_any_status(self):
        module = "okr_management.okr_management.doctype.okr_check_in.okr_check_in"
        with patch(module + ".is_okr_admin", return_value=False), patch(module + "._", side_effect=lambda value: value), patch("frappe.throw", side_effect=frappe.ValidationError):
            for status in ("Draft", "In Progress", "Submitted"):
                with self.assertRaises(frappe.ValidationError):
                    OKRCheckIn.on_trash(frappe._dict(status=status))

    def test_role_metadata_grants_delete_to_both_admin_roles_only(self):
        metadata = json.loads(Path(__file__).with_name("okr_check_in.json").read_text())
        permissions = {row["role"]: row for row in metadata["permissions"]}
        for role in ("OKR Admin", "System Manager"):
            self.assertEqual(permissions[role].get("delete"), 1)
        self.assertFalse(permissions["OKR User"].get("delete"))

    def test_objective_delete_requires_admin_and_preserves_link_guard(self):
        from okr_management.okr_management.doctype.okr_objective.okr_objective import OKRObjective
        from unittest.mock import Mock
        module = "okr_management.okr_management.doctype.okr_objective.okr_objective"
        objective = Mock()
        with patch(module + "._", side_effect=lambda value: value), patch("frappe.throw", side_effect=frappe.ValidationError):
            with patch(module + ".is_okr_admin", return_value=False):
                with self.assertRaises(frappe.ValidationError):
                    OKRObjective.on_trash(objective)
                objective.has_key_results.assert_not_called()
            with patch(module + ".is_okr_admin", return_value=True):
                objective.has_key_results.return_value = False
                OKRObjective.on_trash(objective)
                objective.has_key_results.return_value = True
                with self.assertRaises(frappe.ValidationError):
                    OKRObjective.on_trash(objective)

    def test_objective_standard_delete_permissions(self):
        path = Path(__file__).parent.parent / "okr_objective" / "okr_objective.json"
        permissions = {row["role"]: row for row in json.loads(path.read_text())["permissions"]}
        for role in ("OKR Admin", "System Manager"):
            self.assertEqual(permissions[role].get("delete"), 1)
        self.assertFalse(permissions["OKR User"].get("delete"))
