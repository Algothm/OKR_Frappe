frappe.ui.form.on('OKR Check In', {
	onload(frm) {
		apply_route_context(frm);
	},
	refresh(frm) {
		apply_route_context(frm);
		apply_fast_checkin_ui(frm);
		fetch_and_cache_parent_plan_title(frm);

		if (frm.is_new() && frm.doc.key_result) {
			fill_from_key_result(frm);
		}
	},
	after_save(frm) {
		if (frm.doc.key_result) {
			frappe.kr_needs_reload = true;
			frappe.set_route('Form', 'OKR Key Result', frm.doc.key_result);
		}
	},
	key_result(frm) {
		fill_from_key_result(frm);
	},
	progress(frm) {
		frm.set_value('current_value', frm.doc.progress || 0);
	}
});

function apply_fast_checkin_ui(frm) {
	frm.set_df_property('naming_series', 'hidden', 1);
	frm.set_value('status', 'Submitted');
	if (!frm.doc.reported_by) {
		frm.set_value('reported_by', frappe.session.user);
	}
	if (!frm.doc.checkin_date) {
		frm.set_value('checkin_date', frappe.datetime.get_today());
	}
	['key_result', 'objective', 'parent_plan', 'parent_sprint', 'company', 'department', 'checkin_date', 'reported_by'].forEach(field => {
		frm.set_df_property(field, 'read_only', 1);
	});
	['financial_year', 'current_value', 'confidence', 'next_steps', 'notes', 'status', 'self_rating',
		'action_items_section', 'action_items', 'dependency_section', 'has_dependency', 'dependent_department',
		'impact_level', 'escalation_section', 'escalate_to_department', 'reason_for_escalation',
		'expected_resolution_date', 'summary_sidebar_section', 'review_status', 'manager_feedback',
		'action_required', 'review_date', 'reviewed_by', 'technical_section'].forEach(field => {
		if (frm.fields_dict[field]) {
			frm.set_df_property(field, 'hidden', 1);
		}
	});
	frm.set_df_property('progress', 'read_only', 0);
	frm.toggle_reqd('progress', true);
	frm.toggle_reqd('achievements', true);
}

function apply_route_context(frm) {
	if (!frm.is_new()) {
		return;
	}

	const route_options = frappe.route_options || {};
	if (route_options.action_item) {
		frm.action_item_filter = route_options.action_item;
	} else if (frappe.okr_checkin_action_item) {
		frm.action_item_filter = frappe.okr_checkin_action_item;
	}
	frappe.okr_checkin_action_item = null;

	Object.keys(route_options).forEach(key => {
		const value = route_options[key];
		if (value !== undefined && value !== null && value !== '' && frm.fields_dict[key]) {
			frm.set_value(key, value);
		}
	});

	frappe.route_options = null;
}

function fill_from_key_result(frm) {
	if (!frm.doc.key_result) return;

	let action_item_id = frm.action_item_filter;
	let filters = { parent_key_result: frm.doc.key_result };
	if (action_item_id) {
		filters.name = action_item_id;
	}

	frappe.db.get_value('OKR Key Result', frm.doc.key_result, [
		'objective', 'parent_sprint', 'parent_plan', 'financial_year', 'company', 'department'
	]).then(r => {
		const kr = r.message || {};
		if (kr.objective) frm.set_value('objective', kr.objective);
		if (kr.parent_sprint) frm.set_value('parent_sprint', kr.parent_sprint);
		if (kr.parent_plan) {
			frm.set_value('parent_plan', kr.parent_plan);
			frappe.db.get_value('OKR Plan', kr.parent_plan, 'plan_name').then(p => {
				if (p.message && p.message.plan_name) {
					frappe.utils.add_link_title('OKR Plan', kr.parent_plan, p.message.plan_name);
				}
				frm.refresh_field('parent_plan');
			});
		}
		if (kr.financial_year) frm.set_value('financial_year', kr.financial_year);
		if (kr.company) frm.set_value('company', kr.company);
		if (kr.department) frm.set_value('department', kr.department);
		if (!frm.doc.reported_by) frm.set_value('reported_by', frappe.session.user);
	});

	frappe.db.get_list('OKR Action Item', {
		filters: filters,
		fields: ['name', 'action_item_title', 'owner_user', 'status', 'progress', 'due_date', 'notes', 'parent_key_result'],
		order_by: 'creation asc',
		limit: action_item_id ? 1 : 100
	}).then(items => {
		frm.clear_table('action_items');
		(items || []).forEach(item => {
			const row = frm.add_child('action_items');
			row.name = item.name;
			row.action_item_id = item.name;
			row.parent_key_result = item.parent_key_result;
			row.action_item_title = item.action_item_title;
			row.owner_user = item.owner_user;
			row.status = item.status;
			row.progress = item.progress;
			row.due_date = item.due_date;
			row.notes = item.notes;
		});
		frm.refresh_field('action_items');
	});
}

function toggle_dependency_fields(frm) {
	const has_dep = frm.doc.has_dependency;
	frm.toggle_reqd('dependent_department', has_dep);
	frm.toggle_reqd('dependency_description', has_dep);
	['dependent_department', 'dependency_description', 'impact_level'].forEach(field => {
		frm.toggle_display(field, has_dep);
	});
}

function toggle_escalation_fields(frm) {
	const is_escalated = (frm.doc.review_status === 'Escalated');
	frm.toggle_display('escalation_section', is_escalated);
	['escalate_to_department', 'reason_for_escalation', 'expected_resolution_date'].forEach(field => {
		frm.toggle_display(field, is_escalated);
		frm.toggle_reqd(field, is_escalated);
	});
}

function fetch_and_cache_parent_plan_title(frm) {
	if (frm.doc.parent_plan) {
		frappe.db.get_value('OKR Plan', frm.doc.parent_plan, 'plan_name').then(r => {
			if (r.message && r.message.plan_name) {
				frappe.utils.add_link_title('OKR Plan', frm.doc.parent_plan, r.message.plan_name);
				frm.refresh_field('parent_plan');
			}
		});
	}
}


