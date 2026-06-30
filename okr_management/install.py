from __future__ import annotations

import frappe


def before_install() -> None:
	pass


def after_install() -> None:
	create_roles()
	create_defaults()
	create_workflows()
	create_workspace()


def create_roles() -> None:
	roles = [
		"OKR Admin",
		"OKR Manager",
		"Department Head",
		"Team Lead",
		"Employee",
		"Reviewer",
		"Executive Viewer",
		"HRBP",
	]
	for role in roles:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def create_defaults() -> None:
	if not frappe.db.exists("OKR Settings", "OKR Settings"):
		frappe.get_doc({"doctype": "OKR Settings"}).insert(ignore_permissions=True)


def create_workflows() -> None:
	workflow_definitions = [
		{
			"workflow_name": "OKR Objective Workflow",
			"document_type": "OKR Objective",
			"workflow_state_field": "status",
			"states": [
				{"state": "Draft", "doc_status": 0, "allow_edit": "Employee"},
				{"state": "Submitted", "doc_status": 0, "allow_edit": "OKR Manager"},
				{"state": "Approved", "doc_status": 1, "allow_edit": "OKR Manager"},
				{"state": "Active", "doc_status": 1, "allow_edit": "Employee"},
				{"state": "At Risk", "doc_status": 1, "allow_edit": "Employee"},
				{"state": "Completed", "doc_status": 1, "allow_edit": "OKR Manager"},
			],
			"transitions": [
				{"state": "Draft", "action": "Submit", "next_state": "Submitted", "allowed": "Employee"},
				{"state": "Submitted", "action": "Approve", "next_state": "Approved", "allowed": "OKR Manager"},
				{"state": "Approved", "action": "Activate", "next_state": "Active", "allowed": "OKR Manager"},
				{"state": "Active", "action": "Mark At Risk", "next_state": "At Risk", "allowed": "Employee"},
				{"state": "Active", "action": "Complete", "next_state": "Completed", "allowed": "OKR Manager"},
			],
		},
		{
			"workflow_name": "OKR Key Result Approval",
			"document_type": "OKR Key Result",
			"workflow_state_field": "approval_status",
			"states": [
				{"state": "Draft", "doc_status": 0, "allow_edit": "Employee"},
				{"state": "Pending Approval", "doc_status": 0, "allow_edit": "OKR Manager"},
				{"state": "Approved", "doc_status": 0, "allow_edit": "OKR Manager"},
				{"state": "Returned for Changes", "doc_status": 0, "allow_edit": "Employee"},
				{"state": "Rejected", "doc_status": 0, "allow_edit": "OKR Manager"},
			],
			"transitions": [
				{"state": "Draft", "action": "Submit for Approval", "next_state": "Pending Approval", "allowed": "Employee"},
				{"state": "Returned for Changes", "action": "Submit for Approval", "next_state": "Pending Approval", "allowed": "Employee"},
				{"state": "Pending Approval", "action": "Approve", "next_state": "Approved", "allowed": "OKR Manager"},
				{"state": "Pending Approval", "action": "Reject", "next_state": "Rejected", "allowed": "OKR Manager"},
				{"state": "Pending Approval", "action": "Return for Changes", "next_state": "Returned for Changes", "allowed": "OKR Manager"},
			],
		},
	]

	for definition in workflow_definitions:
		if frappe.db.exists("Workflow", definition["workflow_name"]):
			continue
		workflow = frappe.get_doc(
			{
				"doctype": "Workflow",
				"workflow_name": definition["workflow_name"],
				"document_type": definition["document_type"],
				"workflow_state_field": definition["workflow_state_field"],
				"is_active": 1,
				"send_email_alert": 1,
				"states": definition["states"],
				"transitions": definition["transitions"],
			}
		)
		workflow.insert(ignore_permissions=True)


def create_workspace() -> None:
	from okr_management.rebuild_workspace import run as rebuild_workspaces
	rebuild_workspaces()
