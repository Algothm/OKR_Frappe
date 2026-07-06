import frappe

def run():
    for name in ["OKR Plan", "OKR Sprint", "OKR Objective", "OKR Key Result"]:
        if frappe.db.exists("Workspace", name):
            doc = frappe.get_doc("Workspace", name)
            print(f"\n=== WORKSPACE: {name} ===")
            print(f"Name: {doc.name}")
            print(f"Title: {doc.title}")
            print(f"Parent Page: {doc.parent_page}")
            print(f"Is Hidden: {doc.is_hidden}")
            print(f"Public: {doc.public}")
            print(f"Links count: {len(doc.links) if doc.links else 0}")
            print(f"Shortcuts count: {len(doc.shortcuts) if doc.shortcuts else 0}")
            if doc.links:
                for link in doc.links:
                    print(f"  Link -> Label: {link.label} | Link To: {link.link_to} | Link Type: {link.link_type}")
            if doc.shortcuts:
                for sc in doc.shortcuts:
                    print(f"  Shortcut -> Label: {sc.label} | Link To: {sc.link_to} | Type: {sc.type}")
        else:
            print(f"\n=== WORKSPACE: {name} (DOES NOT EXIST) ===")
