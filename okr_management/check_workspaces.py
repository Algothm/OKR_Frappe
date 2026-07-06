import frappe

def run():
    print("--- WORKSPACES ---")
    workspaces = frappe.get_all("Workspace", fields=["name", "title", "parent_page", "public", "is_hidden"])
    for w in workspaces:
        print(f"Name: {w.name} | Title: {w.title} | Parent: {w.parent_page} | Public: {w.public} | Hidden: {w.is_hidden}")
        
    print("\n--- PAGES ---")
    pages = frappe.get_all("Page", fields=["name", "title"])
    for p in pages:
        print(f"Name: {p.name} | Title: {p.title}")
        
    print("\n--- DOCTYPES ---")
    doctypes = ["OKR Plan", "OKR Sprint", "OKR Objective", "OKR Key Result"]
    for dt in doctypes:
        exists = frappe.db.exists("DocType", dt)
        print(f"DocType: {dt} | Exists: {exists}")
