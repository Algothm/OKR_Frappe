import frappe

@frappe.whitelist()
def get_analytics_data():
    return {}
