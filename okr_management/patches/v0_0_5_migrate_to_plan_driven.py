from __future__ import annotations

import frappe


def execute():
	# 1. Check if the legacy OKR Cycle table exists. If not, skip data migration.
	if not frappe.db.table_exists("OKR Cycle"):
		print("OKR Cycle table does not exist. Skipping data migration.")
		return

	print("Running Plan-driven architecture data migration...")

	# Helper to find or create a fiscal year
	def get_or_create_fiscal_year(start_date, end_date):
		if not start_date or not end_date:
			# Fallback to the first existing fiscal year
			fallback = frappe.db.get_value("Fiscal Year", {}, "name")
			if fallback:
				return fallback
			# Create a default
			fy_doc = frappe.get_doc({
				"doctype": "Fiscal Year",
				"year": "2026-2027",
				"year_start_date": "2026-04-01",
				"year_end_date": "2027-03-31"
			})
			fy_doc.insert(ignore_permissions=True)
			return "2026-2027"

		# Try to find overlapping fiscal year
		fy = frappe.db.get_value("Fiscal Year", {"year_start_date": ["<=", start_date], "year_end_date": [">=", end_date]})
		if fy:
			return fy

		if hasattr(start_date, "year"):
			year = start_date.year
		else:
			year = int(str(start_date)[:4])

		year_str = f"{year}-{year + 1}"
		if frappe.db.exists("Fiscal Year", year_str):
			return year_str

		# Create one
		try:
			fy_doc = frappe.get_doc({
				"doctype": "Fiscal Year",
				"year": year_str,
				"year_start_date": f"{year}-04-01",
				"year_end_date": f"{year + 1}-03-31"
			})
			fy_doc.insert(ignore_permissions=True)
			return year_str
		except Exception:
			# Fallback to any existing fiscal year
			fallback = frappe.db.get_value("Fiscal Year", {}, "name")
			return fallback or "2026-2027"

	# Get all legacy cycles
	cycle_fields = ["name", "cycle_name", "start_date", "end_date", "status", "description", "owner", "creation", "modified"]
	if frappe.db.has_column("OKR Cycle", "progress"):
		cycle_fields.append("progress")

	cycles = frappe.get_all(
		"OKR Cycle",
		fields=cycle_fields
	)

	cycle_to_sprint_map = {}
	cycle_to_plan_map = {}

	# Migrate each OKR Cycle to OKR Plan and OKR Sprint
	for cycle in cycles:
		# Check if already migrated
		existing_plan = frappe.db.get_value("OKR Plan", {"plan_name": cycle.cycle_name or cycle.name})
		if existing_plan:
			print(f"Plan for cycle '{cycle.cycle_name or cycle.name}' already exists. Skipping Plan creation.")
			cycle_to_plan_map[cycle.name] = existing_plan
			# Check for Sprint
			existing_sprint = frappe.db.get_value("OKR Sprint", {"parent_plan": existing_plan})
			if existing_sprint:
				cycle_to_sprint_map[cycle.name] = existing_sprint
				continue

		fiscal_year = get_or_create_fiscal_year(cycle.start_date, cycle.end_date)

		# Map status safely
		status = cycle.status or "Active"
		if status not in ("Draft", "Active", "Completed", "Closed"):
			status = "Active"

		# Create OKR Plan
		plan = frappe.get_doc({
			"doctype": "OKR Plan",
			"plan_name": cycle.cycle_name or cycle.name,
			"financial_year": fiscal_year,
			"status": status,
			"description": cycle.description or "",
			"owner_user": cycle.owner or "Administrator",
			"progress": getattr(cycle, "progress", 0) or 0
		})
		plan.flags.ignore_permissions = True
		plan.insert(ignore_permissions=True)

		# Force preservation of audit metadata fields
		frappe.db.set_value("OKR Plan", plan.name, {
			"owner": cycle.owner,
			"creation": cycle.creation,
			"modified": cycle.modified
		}, update_modified=False)

		# Determine Quarter mapping
		quarter = "Q1"
		for q in ("Q1", "Q2", "Q3", "Q4"):
			if q in (cycle.cycle_name or ""):
				quarter = q
				break

		# Create OKR Sprint
		sprint = frappe.get_doc({
			"doctype": "OKR Sprint",
			"sprint_name": f"{cycle.cycle_name or cycle.name} Sprint",
			"parent_plan": plan.name,
			"quarter": quarter,
			"start_date": cycle.start_date or "2026-01-01",
			"end_date": cycle.end_date or "2026-03-31",
			"status": status,
			"progress": getattr(cycle, "progress", 0) or 0
		})
		sprint.flags.ignore_permissions = True
		sprint.insert(ignore_permissions=True)

		# Force preservation of audit metadata fields
		frappe.db.set_value("OKR Sprint", sprint.name, {
			"owner": cycle.owner,
			"creation": cycle.creation,
			"modified": cycle.modified
		}, update_modified=False)

		cycle_to_sprint_map[cycle.name] = sprint.name
		cycle_to_plan_map[cycle.name] = plan.name
		print(f"Migrated OKR Cycle '{cycle.name}' -> Plan '{plan.name}', Sprint '{sprint.name}'")

	# 2. Re-parent Objectives from Cycle to Sprint
	objectives = frappe.get_all("OKR Objective", fields=["name", "cycle", "sprint"])
	for obj in objectives:
		# Only update if sprint not set and cycle is available in map
		if not obj.sprint and obj.cycle and obj.cycle in cycle_to_sprint_map:
			new_sprint = cycle_to_sprint_map[obj.cycle]
			frappe.db.set_value("OKR Objective", obj.name, "sprint", new_sprint, update_modified=False)
			print(f"Re-parented OKR Objective '{obj.name}' to Sprint '{new_sprint}'")

	# 3. Associate legacy standalone Action Items with Key Result child table parent fields
	# Check if key_result column exists on tabOKR Action Item
	if frappe.db.has_column("OKR Action Item", "key_result"):
		# Count standalone action items to be associated
		standalone_count = frappe.db.sql(
			"""
			select count(*) as count
			from `tabOKR Action Item`
			where (parent is null or parent = '') and key_result is not null and key_result != ''
			""",
			as_dict=True
		)[0].count

		if standalone_count > 0:
			frappe.db.sql(
				"""
				update `tabOKR Action Item`
				set parent = key_result, parenttype = 'OKR Key Result', parentfield = 'action_items'
				where (parent is null or parent = '') and key_result is not null and key_result != ''
				"""
			)
			print(f"Successfully converted {standalone_count} standalone Action Items into OKR Key Result child table rows.")

	frappe.db.commit()
	frappe.clear_cache()
	print("Data migration completed successfully.")
