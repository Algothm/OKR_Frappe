import frappe


def execute():
    frappe.db.sql("""update `tabOKR Key Result` set assignee = owner_user where (assignee is null or assignee = '') and owner_user is not null and owner_user != ''""")
    frappe.db.sql("""update `tabOKR Key Result` set owner_user = assignee where assignee is not null and assignee != '' and (owner_user is null or owner_user != assignee)""")
