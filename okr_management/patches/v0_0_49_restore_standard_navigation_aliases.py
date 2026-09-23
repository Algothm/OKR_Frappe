from __future__ import annotations

from pathlib import Path

import frappe
from frappe.modules.import_file import import_file_by_path


ALIAS_PAGES = (
	"okr_admin_workspace/okr_admin_workspace.json",
	"objective/objective.json",
	"key_result/key_result.json",
)


def execute() -> None:
	"""Restore permanent Page aliases for workspace titles whose routes differ."""
	page_root = Path(frappe.get_app_path("okr_management")) / "okr_management" / "page"
	for relative_path in ALIAS_PAGES:
		import_file_by_path(
			str(page_root / relative_path),
			force=True,
			ignore_version=True,
		)
	frappe.clear_cache()