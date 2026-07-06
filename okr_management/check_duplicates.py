import frappe

def run():
    print("=== ALL WORKSPACES IN DB ===")
    workspaces = frappe.get_all("Workspace", fields=["name", "title", "parent_page", "public", "for_user", "is_hidden"])
    for w in workspaces:
        if "OKR" in w.name or "Planning" in w.name or "Execution" in w.name:
            print(f"Name: {w.name} | Title: {w.title} | Parent: {w.parent_page} | Public: {w.public} | User: {w.for_user} | Hidden: {w.is_hidden}")
            
if __name__ == "__main__":
    run()
