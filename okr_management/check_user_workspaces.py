import frappe
from frappe.desk.desktop import get_workspace_sidebar_items

def run():
    users = frappe.get_all("User", filters={"enabled": 1}, fields=["name", "email", "first_name"])
    print("=== USERS & ROLES ===")
    for u in users:
        roles = frappe.get_roles(u.name)
        print(f"User: {u.name} ({u.first_name}) | Roles: {roles}")
        
        # Get allowed workspaces
        frappe.set_user(u.name)
        res = get_workspace_sidebar_items()
        allowed = [p.name for p in res.get("pages", [])]
        print(f"  Allowed Workspaces ({len(allowed)}): {allowed}")
        
if __name__ == "__main__":
    run()
