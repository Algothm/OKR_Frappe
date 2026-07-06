import frappe

def run():
    print("=== CLIENT SCRIPTS ===")
    scripts = frappe.get_all("Client Script", fields=["name", "dt"])
    for s in scripts:
        print(f"Name: {s.name} | DocType: {s.dt}")
        
    print("\n=== CUSTOM SCRIPTS ===")
    if frappe.db.exists("DocType", "Custom Script"):
        custom_scripts = frappe.get_all("Custom Script", fields=["name", "dt"])
        for cs in custom_scripts:
            print(f"Name: {cs.name} | DocType: {cs.dt}")
    else:
        print("Custom Script DocType does not exist.")
