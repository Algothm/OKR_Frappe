import frappe
from frappe.desk.desktop import get_workspace_sidebar_items

def run():
    frappe.set_user("Administrator")
    res = get_workspace_sidebar_items()
    print("Allowed workspace names returned to client:")
    for page in res.get("pages", []):
        print(f"Name: {page.name} | Title: {page.title} | Parent: {page.parent_page} | Public: {page.public}")
