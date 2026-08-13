import frappe


def execute():
    frappe.db.sql(
        """
        update `tabOKR Plan Team Member`
        set role = 'Plan Coordinator'
        where role = 'Admin'
        """
    )
