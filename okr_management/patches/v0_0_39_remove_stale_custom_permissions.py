import frappe


OBSOLETE_DOCTYPES = (
    "OKR Approval Matrix",
    "OKR Cycle",
    "OKR Cycle Review",
)


def execute():
    """Remove site overrides that conflict with the current OKR permission model."""
    frappe.db.delete("Custom DocPerm", {"parent": "OKR Plan"})
    frappe.db.delete("Custom DocPerm", {"parent": ["in", OBSOLETE_DOCTYPES]})
    frappe.db.delete("Page", {"name": "okr-analytics"})
    frappe.clear_cache()
