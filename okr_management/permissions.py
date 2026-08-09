from __future__ import annotations

import frappe

EXECUTIVE_ROLES = {"System Manager", "OKR Admin", "CEO"}
DEPARTMENT_HEAD_ROLES = {"Department Head", "OKR Department Head"}
MANAGER_ROLES = {"Manager", "OKR Manager"}
EMPLOYEE_ROLES = {"Employee", "OKR Employee"}


def _roles(user: str | None = None) -> set[str]:
	return set(frappe.get_roles(user or frappe.session.user))


def _has_any_role(user: str | None, *roles: str) -> bool:
	return not _roles(user).isdisjoint(set(roles))


def _is_executive(user: str | None = None) -> bool:
	return not _roles(user).isdisjoint(EXECUTIVE_ROLES)


def _is_department_head(user: str | None = None) -> bool:
	return not _roles(user).isdisjoint(DEPARTMENT_HEAD_ROLES)


def _is_manager(user: str | None = None) -> bool:
	return not _roles(user).isdisjoint(MANAGER_ROLES)


def _escape(value: str) -> str:
	return frappe.db.escape(value)


def _in(values: list[str] | set[str]) -> str:
	values = sorted({value for value in values if value})
	return ", ".join(_escape(value) for value in values) if values else "''"


def _company_clause(doctype: str, fieldname: str = "company") -> str:
	company = frappe.defaults.get_user_default("Company")
	if not company:
		return ""
	return f"`tab{doctype}`.`{fieldname}` = {_escape(company)}"


def _user_departments(user: str | None = None) -> list[str]:
	user = user or frappe.session.user
	return frappe.get_all("Employee", filters={"user_id": user}, pluck="department")


def _department_clause(doctype: str, fieldname: str = "department", user: str | None = None) -> str:
	departments = _user_departments(user)
	if not departments:
		return ""
	return f"`tab{doctype}`.`{fieldname}` in ({_in(departments)})"


def _employee_names_for_user(user: str) -> list[str]:
	return frappe.get_all("Employee", filters={"user_id": user}, pluck="name")


def _team_users(user: str | None = None) -> list[str]:
	"""Return current user and employees reporting to them, recursively when Employee.reports_to is available."""
	user = user or frappe.session.user
	team = {user}
	manager_employee_names = set(_employee_names_for_user(user))
	seen_employees = set(manager_employee_names)

	while manager_employee_names:
		reports = frappe.get_all(
			"Employee",
			filters={"reports_to": ["in", list(manager_employee_names)]},
			fields=["name", "user_id"],
			limit_page_length=1000,
		)
		next_manager_names = set()
		for employee in reports:
			if employee.name in seen_employees:
				continue
			seen_employees.add(employee.name)
			next_manager_names.add(employee.name)
			if employee.user_id:
				team.add(employee.user_id)
		manager_employee_names = next_manager_names

	return sorted(team)


def _owner_or_department_clause(doctype: str, owner_field: str = "owner_user", department_field: str = "department", user: str | None = None) -> str:
	user = user or frappe.session.user
	clauses = []
	if _is_department_head(user):
		department_clause = _department_clause(doctype, department_field, user)
		if department_clause:
			clauses.append(department_clause)
	if _is_manager(user):
		clauses.append(f"`tab{doctype}`.`{owner_field}` in ({_in(_team_users(user))})")
	if not clauses:
		clauses.append(f"`tab{doctype}`.`{owner_field}` = {_escape(user)}")
	return "(" + " or ".join(clauses) + ")"


def get_plan_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _is_executive(user) or _is_manager(user):
		return ""
	escaped_user = _escape(user)
	return f"""(
		`tabOKR Plan`.status != 'Draft'
		or `tabOKR Plan`.owner_user = {escaped_user}
		or exists (
			select 1 from `tabOKR Plan Team Member` member
			where member.parent = `tabOKR Plan`.name and member.member_user = {escaped_user}
		)
		or exists (
			select 1 from `tabOKR Objective` objective
			where objective.parent_plan = `tabOKR Plan`.name and objective.owner_user = {escaped_user}
		)
		or exists (
			select 1 from `tabOKR Key Result` kr
			where kr.parent_plan = `tabOKR Plan`.name and kr.assignee = {escaped_user}
		)
		or exists (
			select 1 from `tabOKR Action Item` action
			inner join `tabEmployee` employee on employee.name = action.assigned_to
			where action.parent_plan = `tabOKR Plan`.name and employee.user_id = {escaped_user}
		)
	)"""


def has_plan_permission(doc, user: str | None = None, permission_type: str | None = None):
	user = user or frappe.session.user
	if doc.status != "Draft" or _is_executive(user) or _is_manager(user):
		return None
	if doc.owner_user == user:
		return True
	if frappe.db.exists("OKR Plan Team Member", {"parent": doc.name, "member_user": user}):
		return True
	if frappe.db.exists("OKR Objective", {"parent_plan": doc.name, "owner_user": user}):
		return True
	if frappe.db.exists("OKR Key Result", {"parent_plan": doc.name, "assignee": user}):
		return True
	employees = _employee_names_for_user(user)
	if employees and frappe.db.exists(
		"OKR Action Item", {"parent_plan": doc.name, "assigned_to": ["in", employees]}
	):
		return True
	return False


def get_objective_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _is_executive(user):
		return ""

	clauses = []
	if _is_department_head(user):
		department_clause = _department_clause("OKR Objective", user=user)
		if department_clause:
			clauses.append(department_clause)
	if _is_manager(user):
		users = _team_users(user)
		clauses.extend([
			f"`tabOKR Objective`.owner_user in ({_in(users)})",
			f"exists (select 1 from `tabOKR Key Result` kr where kr.objective = `tabOKR Objective`.name and kr.owner_user in ({_in(users)}))"
		])
	if not clauses:
		clauses.extend([
			f"`tabOKR Objective`.owner_user = {_escape(user)}",
			f"exists (select 1 from `tabOKR Key Result` kr where kr.objective = `tabOKR Objective`.name and kr.owner_user = {_escape(user)})"
		])
	return "(" + " or ".join(clauses) + ")"


def get_key_result_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _is_executive(user):
		return ""

	clauses = []
	if _is_department_head(user):
		departments = _user_departments(user)
		if departments:
			clauses.append(
				f"exists (select 1 from `tabOKR Objective` obj where obj.name = `tabOKR Key Result`.objective and obj.department in ({_in(departments)}))"
			)
	if _is_manager(user):
		users = _team_users(user)
		clauses.extend([
			f"`tabOKR Key Result`.owner_user in ({_in(users)})",
			f"exists (select 1 from `tabOKR Objective` obj where obj.name = `tabOKR Key Result`.objective and obj.owner_user in ({_in(users)}))"
		])
	if not clauses:
		clauses.append(f"`tabOKR Key Result`.owner_user = {_escape(user)}")
	return "(" + " or ".join(clauses) + ")"


def get_action_item_permission_query_conditions(user: str | None = None) -> str:
	return ""


def get_checkin_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _is_executive(user):
		return ""
	clauses = []
	if _is_department_head(user):
		departments = _user_departments(user)
		if departments:
			clauses.append(
				f"exists (select 1 from `tabOKR Objective` obj where obj.name = `tabOKR Check In`.objective and obj.department in ({_in(departments)}))"
			)
	if _is_manager(user):
		users = _team_users(user)
		clauses.append(f"`tabOKR Check In`.reported_by in ({_in(users)})")
		clauses.append(f"exists (select 1 from `tabOKR Key Result` kr where kr.name = `tabOKR Check In`.key_result and kr.owner_user in ({_in(users)}))")
	if not clauses:
		clauses.append(f"`tabOKR Check In`.reported_by = {_escape(user)}")
	return "(" + " or ".join(clauses) + ")"
