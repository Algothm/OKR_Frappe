from pathlib import Path

import frappe
from frappe.modules.import_file import import_file_by_path


WORKSPACE_FILES = [
    'okr_management/okr_management.json',
    'planning/planning.json',
    'execution/execution.json',
    'administration/administration.json',
]


def execute():
    base = Path(frappe.get_app_path('okr_management')) / 'okr_management' / 'workspace'
    for relative_path in WORKSPACE_FILES:
        import_file_by_path(str(base / relative_path), force=True, ignore_version=True)
    frappe.clear_cache()
