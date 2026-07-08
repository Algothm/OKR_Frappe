import frappe


ROOT_WORKSPACE = "OKR Management"
STALE_ROOT_WORKSPACES = ["Wiki Website", "Work item Task", "Work Item Task"]

WORKSPACES = [
    {
        "name": "Planning",
        "title": "Planning",
        "label": "Planning",
        "parent_page": ROOT_WORKSPACE,
        "icon": "calendar",
        "sequence_id": 2,
        "links": [
            {"label": "OKR Analytics", "link_type": "Page", "link_to": "okr-analytics"},
            {"label": "OKR Plan", "link_type": "DocType", "link_to": "OKR Plan"},
            {"label": "OKR Sprint", "link_type": "DocType", "link_to": "OKR Sprint"},
        ],
        "shortcuts": [
            {"label": "OKR Analytics", "type": "Page", "link_to": "okr-analytics"},
            {"label": "OKR Plan", "type": "DocType", "link_to": "OKR Plan", "doc_view": "List"},
            {"label": "OKR Sprint", "type": "DocType", "link_to": "OKR Sprint", "doc_view": "List"},
        ],
    },
    {
        "name": "OKR Analytics Planning",
        "title": "OKR Analytics",
        "label": "OKR Analytics Planning",
        "parent_page": "Planning",
        "icon": "es-line-chart",
        "sequence_id": 2.1,
        "links": [{"label": "OKR Analytics", "link_type": "Page", "link_to": "okr-analytics"}],
        "shortcuts": [{"label": "OKR Analytics", "type": "Page", "link_to": "okr-analytics"}],
    },
    {
        "name": "OKR Plan Planning",
        "title": "OKR Plan",
        "label": "OKR Plan Planning",
        "parent_page": "Planning",
        "icon": "folder-normal",
        "sequence_id": 2.2,
        "links": [{"label": "OKR Plan", "link_type": "DocType", "link_to": "OKR Plan"}],
        "shortcuts": [{"label": "OKR Plan", "type": "DocType", "link_to": "OKR Plan", "doc_view": "List"}],
    },
    {
        "name": "OKR Sprint Planning",
        "title": "OKR Sprint",
        "label": "OKR Sprint Planning",
        "parent_page": "Planning",
        "icon": "folder-normal",
        "sequence_id": 2.3,
        "links": [{"label": "OKR Sprint", "link_type": "DocType", "link_to": "OKR Sprint"}],
        "shortcuts": [{"label": "OKR Sprint", "type": "DocType", "link_to": "OKR Sprint", "doc_view": "List"}],
    },
    {
        "name": "Execution",
        "title": "Execution",
        "label": "Execution",
        "parent_page": ROOT_WORKSPACE,
        "icon": "project",
        "sequence_id": 3,
        "links": [
            {"label": "OKR Analytics", "link_type": "Page", "link_to": "okr-analytics"},
            {"label": "OKR Objective", "link_type": "DocType", "link_to": "OKR Objective"},
            {"label": "OKR Key Result", "link_type": "DocType", "link_to": "OKR Key Result"},
        ],
        "shortcuts": [
            {"label": "OKR Analytics", "type": "Page", "link_to": "okr-analytics"},
            {"label": "OKR Objective", "type": "DocType", "link_to": "OKR Objective", "doc_view": "List"},
            {"label": "OKR Key Result", "type": "DocType", "link_to": "OKR Key Result", "doc_view": "List"},
        ],
    },
    {
        "name": "OKR Analytics Execution",
        "title": "OKR Analytics",
        "label": "OKR Analytics Execution",
        "parent_page": "Execution",
        "icon": "es-line-chart",
        "sequence_id": 3.1,
        "links": [{"label": "OKR Analytics", "link_type": "Page", "link_to": "okr-analytics"}],
        "shortcuts": [{"label": "OKR Analytics", "type": "Page", "link_to": "okr-analytics"}],
    },
    {
        "name": "OKR Objective Execution",
        "title": "OKR Objective",
        "label": "OKR Objective Execution",
        "parent_page": "Execution",
        "icon": "folder-normal",
        "sequence_id": 3.2,
        "links": [{"label": "OKR Objective", "link_type": "DocType", "link_to": "OKR Objective"}],
        "shortcuts": [{"label": "OKR Objective", "type": "DocType", "link_to": "OKR Objective", "doc_view": "List"}],
    },
    {
        "name": "OKR Key Result Execution",
        "title": "OKR Key Result",
        "label": "OKR Key Result Execution",
        "parent_page": "Execution",
        "icon": "folder-normal",
        "sequence_id": 3.3,
        "links": [{"label": "OKR Key Result", "link_type": "DocType", "link_to": "OKR Key Result"}],
        "shortcuts": [{"label": "OKR Key Result", "type": "DocType", "link_to": "OKR Key Result", "doc_view": "List"}],
    },
]


def execute():
    previous_in_migrate = frappe.flags.in_migrate
    frappe.flags.in_migrate = True
    try:
        ensure_root_workspace()
        remove_stale_root_workspaces()
        for spec in WORKSPACES:
            upsert_workspace(spec)
    finally:
        frappe.flags.in_migrate = previous_in_migrate

    frappe.clear_cache()


def ensure_root_workspace():
    if not frappe.db.exists("Workspace", ROOT_WORKSPACE):
        return

    frappe.db.set_value(
        "Workspace",
        ROOT_WORKSPACE,
        {
            "parent_page": "",
            "module": "OKR Management",
            "public": 1,
            "is_hidden": 0,
            "sequence_id": 1,
        },
        update_modified=False,
    )


def remove_stale_root_workspaces():
    for name in STALE_ROOT_WORKSPACES:
        if not frappe.db.exists("Workspace", name):
            continue

        parent_page, module = frappe.db.get_value("Workspace", name, ["parent_page", "module"])
        if (not parent_page or parent_page == ROOT_WORKSPACE) and (not module or module == "OKR Management"):
            frappe.delete_doc("Workspace", name, force=True, ignore_permissions=True)


def upsert_workspace(spec):
    if frappe.db.exists("Workspace", spec["name"]):
        workspace = frappe.get_doc("Workspace", spec["name"])
    else:
        workspace = frappe.new_doc("Workspace")
        workspace.name = spec["name"]

    workspace.update(
        {
            "label": spec["label"],
            "title": spec["title"],
            "module": "OKR Management",
            "public": 1,
            "for_user": "",
            "hide_custom": 1,
            "icon": spec["icon"],
            "indicator_color": "green",
            "is_hidden": 0,
            "parent_page": spec["parent_page"],
            "sequence_id": spec["sequence_id"],
            "content": workspace.content or "[]",
        }
    )

    workspace.set("links", build_links(spec["links"]))
    workspace.set("shortcuts", build_shortcuts(spec["shortcuts"]))
    workspace.set("charts", [])
    workspace.set("number_cards", [])
    workspace.set("quick_lists", [])
    workspace.set("custom_blocks", [])
    workspace.flags.ignore_permissions = True
    workspace.save(ignore_permissions=True)


def build_links(items):
    links = [{"type": "Card Break", "label": "Links", "hidden": 0, "is_query_report": 0, "onboard": 0}]
    for item in items:
        links.append(
            {
                "type": "Link",
                "label": item["label"],
                "link_type": item["link_type"],
                "link_to": item["link_to"],
                "hidden": 0,
                "is_query_report": 0,
                "onboard": 0,
            }
        )
    return links


def build_shortcuts(items):
    shortcuts = []
    for item in items:
        shortcut = {
            "label": item["label"],
            "type": item["type"],
            "link_to": item["link_to"],
            "doc_view": item.get("doc_view", ""),
        }
        shortcuts.append(shortcut)
    return shortcuts
