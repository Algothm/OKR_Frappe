import frappe
import json

def run():
    for name in ["OKR Plan", "OKR Sprint"]:
        doc = frappe.get_doc("Workspace", name)
        print(f"\n=================== WORKSPACE: {name} ===================")
        print(json.dumps(doc.as_dict(), indent=4, default=str))
        
    print("\n=================== DOCTYPES ===================")
    for name in ["OKR Plan", "OKR Sprint"]:
        doc = frappe.get_doc("DocType", name)
        print(f"DocType: {name} | Custom: {doc.custom} | Track Changes: {doc.track_changes}")
