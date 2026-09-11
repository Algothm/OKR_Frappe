from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


class TestOKRUserFacingLabels(FrappeTestCase):
	def test_action_item_and_checkin_status_options_use_done(self):
		action_options = frappe.get_meta("OKR Action Item").get_field("status").options.splitlines()
		checkin_options = frappe.get_meta("OKR Check In").get_field("action_status").options.splitlines()

		self.assertIn("Done", action_options)
		self.assertNotIn("Archived", action_options)
		self.assertEqual(checkin_options, ["In Progress", "On Hold", "Done", "Blocked"])

	def test_workspace_status_dropdown_has_exact_order_and_no_archived_option(self):
		source = Path(
			frappe.get_app_path(
				"okr_management",
				"okr_management",
				"page",
				"okr_workspace",
				"okr_workspace.js",
			)
		).read_text(encoding="utf-8")
		panel = source[source.index('<select class="form-control" data-ws-status>') :]
		panel = panel[: panel.index("</select>")]

		positions = [panel.index(f'<option value="{status}"') for status in (
			"In Progress", "On Hold", "Done", "Blocked"
		)]
		self.assertEqual(positions, sorted(positions))
		self.assertNotIn('<option value="Archived"', panel)
		self.assertNotIn('__("Archived")', panel)

	def test_measurement_lock_label_changed_without_fieldname_or_behavior_change(self):
		field = frappe.get_meta("OKR Key Result").get_field(
			"lock_measurement_fields_for_action_item_assignees"
		)
		self.assertEqual(field.fieldname, "lock_measurement_fields_for_action_item_assignees")
		self.assertEqual(field.label, "Allow Assignees to Edit Their Action Item Measurement")
		self.assertEqual(field.default, "1")
		self.assertEqual(frappe.get_meta("OKR Key Result").get_field("calculation_mode").default, "Automatic")

	def test_measurement_type_displays_amount_while_preserving_currency_value(self):
		for doctype in ("OKR Key Result", "OKR Action Item"):
			source = Path(frappe.get_app_path(
				"okr_management", "okr_management", "doctype",
				frappe.scrub(doctype), f"{frappe.scrub(doctype)}.js",
			)).read_text(encoding="utf-8")
			self.assertIn("{ label: __(\"Amount\"), value: \"Currency\" }", source.replace("'", '"'))
			self.assertNotIn("{ label: __(\"Currency\"), value: \"Currency\" }", source.replace("'", '"'))

	def test_workspace_percentage_uses_direct_progress_while_amount_keeps_raw_current_value(self):
		source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "page", "okr_workspace", "okr_workspace.js",
		)).read_text(encoding="utf-8")
		self.assertIn('__("Current Progress (%)")', source)
		self.assertNotIn('__("Current Percentage (%)")', source)
		self.assertIn('const actual = metricType === "Percentage" ? completionDisplay : rawActual;', source)
		self.assertIn("const currentValue = enteredValue;", source)
		self.assertNotIn("baseline + ((target - baseline) * enteredValue) / 100", source)
		self.assertIn('this.format_kr_number(row.progress)', source)

	def test_workspace_kr_display_follows_metric_type_and_percentage_uses_child_average(self):
		source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "page", "okr_workspace", "okr_workspace.js",
		)).read_text(encoding="utf-8")
		self.assertIn('if (metricType === "percentage")', source)
		self.assertIn('const completion = (kr.action_items || []).length', source)
		self.assertIn('? kr.target_progress || 0', source)
		self.assertIn('this.format_kr_currency(', source)
		self.assertIn('kr.current_value,', source)
		self.assertIn('this.format_kr_number(kr.current_value)', source)

	def test_key_result_owner_can_edit_raw_current_while_completion_stays_calculated(self):
		source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "doctype", "okr_key_result", "okr_key_result.js",
		)).read_text(encoding="utf-8")
		self.assertIn('frm.set_df_property("current_value", "read_only", 0)', source)
		self.assertNotIn('field.$input.val(progress_text)', source)
		self.assertIn('frm.doc.target_progress || 0', source)

	def test_hierarchy_rows_show_progress_and_kr_form_preserves_child_average(self):
		workspace = Path(frappe.get_app_path(
			"okr_management", "okr_management", "page", "okr_workspace", "okr_workspace.js",
		)).read_text(encoding="utf-8")
		self.assertIn('return `${this.format_kr_number(meas.progress)}%`;', workspace)
		self.assertIn('this.format_kr_currency(meas.current_value, currency)', workspace)
		self.assertIn('this.format_kr_number(meas.current_value)', workspace)
		self.assertIn('this.format_kr_number(meas.target_value)', workspace)
		self.assertIn('const completion = (kr.action_items || []).length', workspace)
		kr_form = Path(frappe.get_app_path(
			"okr_management", "okr_management", "doctype", "okr_key_result", "okr_key_result.js",
		)).read_text(encoding="utf-8")
		self.assertIn('if (cint(frm.doc.action_item_count || 0) > 0)', kr_form)
		self.assertIn('render_measurement_guidance(frm, progress)', kr_form)
		self.assertIn('Action Item average stored in target_progress', kr_form)

	def test_action_form_has_its_own_live_completion_bar(self):
		source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "doctype", "okr_action_item", "okr_action_item.js",
		)).read_text(encoding="utf-8")
		self.assertIn("function render_action_completion(frm, progress_value)", source)
		self.assertIn("render_action_completion(frm, progress)", source)
		self.assertIn("Calculated completion", source)
		self.assertIn("fields_dict.current_value", source)

	def test_customize_measurement_checkbox_is_internal_and_section_is_directly_available(self):
		meta = frappe.get_meta("OKR Action Item")
		field = meta.get_field("customize_measurement")
		section = meta.get_field("measurement_section")
		self.assertEqual(field.fieldname, "customize_measurement")
		self.assertEqual(field.hidden, 1)
		self.assertNotEqual(field.label, "Customize My Measurement")
		self.assertFalse(section.depends_on)

		form_source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "doctype", "okr_action_item", "okr_action_item.js",
		)).read_text(encoding="utf-8")
		self.assertIn("frm.set_df_property('measurement_section', 'hidden', 0)", form_source)
		self.assertIn("frm.set_value('customize_measurement', 1)", form_source)

		workspace_source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "page", "okr_workspace", "okr_workspace.js",
		)).read_text(encoding="utf-8")
		self.assertNotIn("Edit Measurement", workspace_source)
		self.assertNotIn("data-edit-measurement", workspace_source)
		self.assertNotIn("open_measurement_editor", workspace_source)

	def test_key_result_title_is_unlimited_compact_and_decrease_starts_at_baseline(self):
		meta = frappe.get_meta("OKR Key Result")
		self.assertEqual(meta.get_field("key_result_title").fieldtype, "Small Text")

		source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "doctype", "okr_key_result", "okr_key_result.js",
		)).read_text(encoding="utf-8")
		self.assertIn("function setup_auto_growing_key_result_title(frm)", source)
		self.assertIn('Math.max(38, textarea.scrollHeight)', source)
		self.assertIn("function initialize_new_current_from_baseline(frm)", source)
		self.assertIn('frm.set_value("current_value", flt(frm.doc.baseline_value || 0))', source)
		self.assertIn("frm.__current_value_was_edited = true", source)
		self.assertIn("function setup_action_item_connection_route(frm)", source)
		self.assertIn('frappe.route_options = { parent_key_result: frm.doc.name }', source)
		self.assertIn('frappe.new_doc("OKR Action Item")', source)

		unlimited_title_fields = {
			"OKR Plan": ("plan_name",),
			"OKR Objective": ("objective_title", "plan_name"),
			"OKR Key Result": ("key_result_title", "objective_title"),
			"OKR Action Item": (
				"action_item_title", "key_result_title", "objective_title", "plan_title",
			),
			"OKR Check In": ("action_item_title_context",),
		}
		for doctype, fieldnames in unlimited_title_fields.items():
			meta = frappe.get_meta(doctype)
			for fieldname in fieldnames:
				with self.subTest(doctype=doctype, fieldname=fieldname):
					self.assertEqual(meta.get_field(fieldname).fieldtype, "Small Text")

		action_source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "doctype", "okr_action_item", "okr_action_item.js",
		)).read_text(encoding="utf-8")
		plan_source = Path(frappe.get_app_path(
			"okr_management", "okr_management", "doctype", "okr_plan", "okr_plan.js",
		)).read_text(encoding="utf-8")
		self.assertIn("function setup_auto_growing_title(frm, fieldname)", action_source)
		self.assertIn("function setup_auto_growing_plan_title(frm, fieldname)", plan_source)
