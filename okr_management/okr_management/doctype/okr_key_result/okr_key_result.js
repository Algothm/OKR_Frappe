frappe.ui.form.on('OKR Key Result', {
	refresh(frm) {
		apply_key_result_ui(frm);
		fetch_and_cache_parent_plan_title(frm);
		update_objective_date_range(frm);
	},
	objective(frm) {
		populate_objective_context(frm);
	},
	calculation_mode(frm) {
		apply_key_result_ui(frm);
	},
	metric_type(frm) {
		handle_metric_type_change(frm);
		apply_key_result_ui(frm);
	}
});

const INHERITED_FIELDS = [
	'parent_plan',
	'parent_plan',
	'objective_title',
	'company',
	'financial_year',
	'department',
	'plan_owner',
	'plan_owner',
	'objective_owner',
	'objective_level',
	'date_range',
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
		'objective_title',
		'company',
		'financial_year',
		'department',
		'plan_owner',
		'plan_owner',
		'owner_user',
		'level',
		'start_date',
		'end_date'
	]).then(r => {
		const objective = r.message || {};
		frm.set_value('parent_plan', objective.parent_plan || '');
		frm.set_value('parent_plan', objective.parent_plan || '');
		frm.set_value('objective_title', objective.objective_title || '');
		frm.set_value('company', objective.company || '');
		frm.set_value('financial_year', objective.financial_year || '');
		frm.set_value('department', objective.department || '');
		frm.set_value('plan_owner', objective.plan_owner || '');
		frm.set_value('plan_owner', objective.plan_owner || '');
		frm.set_value('objective_owner', objective.owner_user || '');
		frm.set_value('owner_user', objective.owner_user || frappe.session.user || '');
		frm.set_value('objective_level', objective.level || '');
		frm.set_value('start_date', objective.start_date || '');
		frm.set_value('end_date', objective.end_date || '');
		update_objective_date_range(frm, objective.start_date, objective.end_date);

		fetch_and_cache_parent_plan_title(frm);
	});
}

function clear_objective_context(frm) {
	INHERITED_FIELDS.forEach(fieldname => frm.set_value(fieldname, ''));
}

function update_objective_date_range(frm, start_date, end_date) {
	const start = start_date || frm.doc.start_date;
	const end = end_date || frm.doc.end_date;
	if (start === undefined || start === null || start === '' || end === undefined || end === null || end === '') {
		frm.set_value('date_range', '');
		return;
	}

	const days = moment(end).diff(moment(start), 'days') + 1;
	const label = frappe.datetime.str_to_user(start) + ' to ' + frappe.datetime.str_to_user(end)
		+ (days > 0 ? ' (' + days + ' days)' : '');
	frm.set_value('date_range', label);
}

function apply_key_result_ui(frm) {
	frm.set_df_property('naming_series', 'hidden', 1);

	INHERITED_FIELDS.forEach(fieldname => {
		frm.set_df_property(fieldname, 'read_only', 1);
	});
	['owner_user', 'ownership_section', 'ownership_col_break', 'ownership_status_col_break', 'plan_owner', 'objective_owner', 'objective_level', 'start_date', 'end_date'].forEach(fieldname => {
		frm.set_df_property(fieldname, 'hidden', 1);
	});

	['target_progress', 'score', 'action_item_count', 'checkin_count'].forEach(fieldname => {
		frm.set_df_property(fieldname, 'read_only', 1);
	});

	const has_action_items = cint(frm.doc.action_item_count || 0) > 0;
	frm.set_df_property('current_value', 'read_only', has_action_items);
	frm.toggle_display('currency', frm.doc.metric_type === 'Currency');

	const metric_type = frm.doc.metric_type;
	frm.toggle_reqd('target_value', metric_type === 'Percentage');
	frm.set_df_property('unit_of_measure', 'placeholder', 'e.g., Customers, Leads, Orders, Hours, Tasks, Bottles, Calls');

	if (metric_type === 'Boolean') {
		frm.toggle_display('unit_of_measure', 0);
		frm.set_df_property('unit_of_measure', 'read_only', 1);
	} else if (metric_type === 'Percentage') {
		frm.toggle_display('unit_of_measure', 1);
		frm.set_df_property('unit_of_measure', 'read_only', 1);
		if (frm.doc.unit_of_measure != '%') {
			frm.set_value('unit_of_measure', '%');
		}
	} else if (metric_type === 'Number') {
		frm.toggle_display('unit_of_measure', 1);
		frm.set_df_property('unit_of_measure', 'read_only', 0);
		if (frm.doc.unit_of_measure === '%') {
			frm.set_value('unit_of_measure', '');
		}
	} else {
		frm.toggle_display('unit_of_measure', 0);
		frm.set_df_property('unit_of_measure', 'read_only', 1);
	}
}

function handle_metric_type_change(frm) {
	const metric_type = frm.doc.metric_type;
	if (metric_type === 'Percentage') {
		if (frm.doc.target_value === undefined || frm.doc.target_value === null || frm.doc.target_value === 0) {
			frm.set_value('target_value', 100);
		}
		if (!frm.doc.unit_of_measure || frm.doc.unit_of_measure === '') {
			frm.set_value('unit_of_measure', '%');
		}
	} else if (metric_type === 'Boolean') {
		if (frm.doc.target_value !== 0 && frm.doc.target_value !== 1) {
			frm.set_value('target_value', 1);
		}
		frm.set_value('unit_of_measure', '');
	} else if (metric_type === 'Number') {
		if (frm.doc.target_value === 100 || frm.doc.target_value === 1) {
			frm.set_value('target_value', '');
		}
		if (frm.doc.unit_of_measure === '%') {
			frm.set_value('unit_of_measure', '');
		}
	} else if (metric_type === 'Currency') {
		if (frm.doc.target_value === 100 || frm.doc.target_value === 1) {
			frm.set_value('target_value', '');
		}
		frm.set_value('unit_of_measure', '');
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



