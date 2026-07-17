import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    filters = {
        "doc_type": "Employee",
        "doctype_or_field": "DocType",
        "property": "show_title_field_in_link",
    }
    existing = frappe.db.get_value("Property Setter", filters, ["name", "value"], as_dict=True)
    if existing:
        if existing.value != "1":
            frappe.db.set_value("Property Setter", existing.name, "value", "1")
        frappe.clear_cache(doctype="Employee")
        return

    make_property_setter(
        "Employee",
        None,
        "show_title_field_in_link",
        1,
        "Check",
        for_doctype=True,
    )
