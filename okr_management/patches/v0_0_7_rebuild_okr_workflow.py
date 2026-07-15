import frappe


WORKSPACE_LINKS = [
	{'hidden': 0, 'is_query_report': 0, 'label': 'OKR Plan', 'link_to': 'OKR Plan', 'link_type': 'DocType', 'type': 'Link'},
	{'hidden': 0, 'is_query_report': 0, 'label': 'OKR Sprint', 'link_to': 'OKR Sprint', 'link_type': 'DocType', 'type': 'Link'},
	{'hidden': 0, 'is_query_report': 0, 'label': 'Objectives', 'link_to': 'OKR Objective', 'link_type': 'DocType', 'type': 'Link'},
	{'hidden': 0, 'is_query_report': 0, 'label': 'Key Results', 'link_to': 'OKR Key Result', 'link_type': 'DocType', 'type': 'Link'},
]


OBSOLETE_WORKSPACES = [
	'OKR Plan',
	'OKR Sprint',
	'Objectives',
	'Key Results',
	'Executive',
	'Review',
	'Reports',
	'Settings',
	'Dashboard',
	'Performance',
	'Analytics',
	'Hierarchy Tree',
]


def execute():
	for name in OBSOLETE_WORKSPACES:
		if frappe.db.exists('Workspace', name):
			workspace = frappe.get_doc('Workspace', name)
			if workspace.module == 'OKR Management' or workspace.parent_page == 'OKR Management':
				frappe.delete_doc('Workspace', name, force=True, ignore_permissions=True)

	if frappe.db.exists('Workspace', 'OKR Management'):
		workspace = frappe.get_doc('Workspace', 'OKR Management')
	else:
		workspace = frappe.new_doc('Workspace')
		workspace.name = 'OKR Management'

	workspace.update({
		'label': 'OKR Management',
		'title': 'OKR Management',
		'module': 'OKR Management',
		'public': 1,
		'is_standard': 1,
		'for_user': '',
		'hide_custom': 0,
		'icon': 'folder',
		'indicator_color': 'green',
		'is_hidden': 0,
		'parent_page': '',
		'sequence_id': 1,
		'content': '[]',
		'shortcuts': [],
		'charts': [],
		'number_cards': [],
		'links': WORKSPACE_LINKS,
	})
	workspace.flags.ignore_permissions = True
	workspace.save()
	frappe.clear_cache()
