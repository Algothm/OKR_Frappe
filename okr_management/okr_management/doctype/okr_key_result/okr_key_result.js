frappe.ui.form.on('OKR Key Result', {
	refresh(frm) {
		apply_key_result_ui(frm);
		fetch_and_cache_parent_plan_title(frm);
	},
	objective(frm) {
		populate_objective_context(frm);
	},
	calculation_mode(frm) {
		apply_key_result_ui(frm);
	},
	metric_type(frm) {
		apply_key_result_ui(frm);
	}
});

const INHERITED_FIELDS = [
	'parent_plan',
	'parent_sprint',
	'objective_title',
	'company',
	'financial_year',
	'department',
	'plan_owner',
	'sprint_owner',
	'objective_owner',
	'objective_level',
	'start_date',
	'end_date'
];

function populate_objective_context(frm) {
	if (!frm.doc.objective) {
		clear_objective_context(frm);
		return;
	}

	frappe.db.get_value('OKR Objective', frm.doc.objective, [
		'parent_plan',
		'sprint',
		'objective_title',
		'company',
		'financial_year',
		'department',
		'plan_owner',
		'sprint_owner',
		'owner_user',
		'level',
		'start_date',
		'end_date'
	]).then(r => {
		const objective = r.message || {};
		frm.set_value('parent_plan', objective.parent_plan || '');
		frm.set_value('parent_sprint', objective.sprint || '');
		frm.set_value('objective_title', objective.objective_title || '');
		frm.set_value('company', objective.company || '');
		frm.set_value('financial_year', objective.financial_year || '');
		frm.set_value('department', objective.department || '');
		frm.set_value('plan_owner', objective.plan_owner || '');
		frm.set_value('sprint_owner', objective.sprint_owner || '');
		frm.set_value('objective_owner', objective.owner_user || '');
		frm.set_value('objective_level', objective.level || '');
		frm.set_value('start_date', objective.start_date || '');
		frm.set_value('end_date', objective.end_date || '');

		fetch_and_cache_parent_plan_title(frm);
	});
}

function clear_objective_context(frm) {
	INHERITED_FIELDS.forEach(fieldname => frm.set_value(fieldname, ''));
}

function apply_key_result_ui(frm) {
	frm.set_df_property('naming_series', 'hidden', 1);

	INHERITED_FIELDS.forEach(fieldname => {
		frm.set_df_property(fieldname, 'read_only', 1);
	});

	['target_progress', 'score', 'action_item_count', 'checkin_count'].forEach(fieldname => {
		frm.set_df_property(fieldname, 'read_only', 1);
	});

	frm.set_df_property('current_value', 'read_only', frm.doc.calculation_mode !== 'Manual');
	
	// Show Currency only when Measurement Type = Currency. Hide otherwise.
	frm.toggle_display('currency', frm.doc.metric_type === 'Currency');

	// Hide/Disable rules for Unit of Measure
	const metric_type = frm.doc.metric_type;
	if (metric_type === 'Boolean') {
		frm.toggle_display('unit_of_measure', 0);
		frm.set_df_property('unit_of_measure', 'read_only', 1);
	} else if (metric_type === 'Percentage') {
		frm.toggle_display('unit_of_measure', 1);
		frm.set_df_property('unit_of_measure', 'read_only', 1);
		if (frm.is_new() && !frm.doc.unit_of_measure) {
			frm.set_value('unit_of_measure', '%');
		}
	} else if (metric_type === 'Number') {
		frm.toggle_display('unit_of_measure', 1);
		frm.set_df_property('unit_of_measure', 'read_only', 0);
	} else { // Currency
		frm.toggle_display('unit_of_measure', 0);
		frm.set_df_property('unit_of_measure', 'read_only', 1);
	}
}

function fetch_and_cache_parent_plan_title(frm) {
	if (!frm.doc.parent_plan) {
		return;
	}

	frappe.db.get_value('OKR Plan', frm.doc.parent_plan, 'plan_name').then(r => {
		if (r.message && r.message.plan_name) {
			frappe.utils.add_link_title('OKR Plan', frm.doc.parent_plan, r.message.plan_name);
			frm.refresh_field('parent_plan');
		}
	});
}
