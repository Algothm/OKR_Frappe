import frappe


ADMIN_WORKSPACE = "Admin Workspace"
ADMIN_PAGE = "admin-workspace"
ADMIN_ROLES = [
    "System Manager",
    "OKR Admin",
    "OKR Manager",
    "Department Head",
    "Executive Viewer",
    "HR Manager",
]


def execute():
    frappe.reload_doc("okr_management", "page", "admin_workspace")
    ensure_admin_workspace()
    frappe.clear_cache()


def ensure_admin_workspace():
    if frappe.db.exists("Workspace", ADMIN_WORKSPACE):
        workspace = frappe.get_doc("Workspace", ADMIN_WORKSPACE)
    else:
        workspace = frappe.new_doc("Workspace")
        workspace.name = ADMIN_WORKSPACE

    workspace.update(
        {
            "label": ADMIN_WORKSPACE,
            "title": ADMIN_WORKSPACE,
            "module": "OKR Management",
            "public": 1,
            "for_user": "",
            "hide_custom": 1,
            "icon": "folder-normal",
            "indicator_color": "green",
            "is_hidden": 0,
            "parent_page": "Planning",
            "sequence_id": 2.4,
            "content": "[]",
        }
    )
    workspace.set("links", build_links())
    workspace.set("shortcuts", build_shortcuts())
    workspace.set("charts", [])
    workspace.set("number_cards", [])
    workspace.set("quick_lists", [])
    workspace.set("custom_blocks", [])
    workspace.set("roles", [{"role": role} for role in ADMIN_ROLES if frappe.db.exists("Role", role)])
    workspace.flags.ignore_permissions = True
    workspace.save(ignore_permissions=True)


def build_links():
    return [
        {"type": "Card Break", "label": "Links", "hidden": 0, "is_query_report": 0, "onboard": 0},
        {
            "type": "Link",
            "label": ADMIN_WORKSPACE,
            "link_type": "Page",
            "link_to": ADMIN_PAGE,
            "hidden": 0,
            "is_query_report": 0,
            "onboard": 0,
        },
    ]


def build_shortcuts():
    return [{"label": ADMIN_WORKSPACE, "type": "Page", "link_to": ADMIN_PAGE, "doc_view": ""}]
