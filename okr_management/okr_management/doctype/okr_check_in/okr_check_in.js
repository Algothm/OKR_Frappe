frappe.ui.form.on('OKR Check In', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		frm.set_df_property('objective', 'read_only', 1);
		if (!frm.doc.reported_by) {
			frm.set_value('reported_by', frappe.session.user);
		}
		apply_manager_review_permissions(frm);
		toggle_dependency_fields(frm);
		toggle_escalation_fields(frm);
		calculate_checkin_progress_preview(frm);
		render_summary_widget(frm);
	},
	key_result(frm) {
		fill_from_key_result(frm);
		frm.custom_kr_data = null;
		calculate_checkin_progress_preview(frm);
	},
	reported_by(frm) {
		apply_manager_review_permissions(frm);
	},
	current_value(frm) {
		calculate_checkin_progress_preview(frm);
	},
	has_dependency(frm) {
		toggle_dependency_fields(frm);
	},
	review_status(frm) {
		toggle_escalation_fields(frm);
	}
});

function is_okr_manager() {
	return frappe.user.has_role('System Manager') || frappe.user.has_role('OKR Admin') || frappe.user.has_role('OKR Manager') || frappe.user.has_role('Team Lead');
}

function apply_manager_review_permissions(frm) {
	const can_review = is_okr_manager();
	frm.set_df_property('summary_sidebar_section', 'hidden', !can_review && frm.is_new());
	['review_status', 'manager_feedback', 'action_required', 'review_date', 'reviewed_by'].forEach(field => {
		frm.set_df_property(field, 'read_only', !can_review);
		frm.set_df_property(field, 'hidden', !can_review && !frm.doc.reviewed_by);
	});
	frm.set_df_property('reported_by', 'read_only', !can_review);
}

function fill_from_key_result(frm) {
	if (!frm.doc.key_result) return;
	frappe.db.get_value('OKR Key Result', frm.doc.key_result, ['objective', 'department']).then(r => {
		const kr = r.message || {};
		if (kr.objective) frm.set_value('objective', kr.objective);
		if (kr.department) frm.set_value('department', kr.department);
		if (!frm.doc.reported_by) frm.set_value('reported_by', frappe.session.user);
	});

	// Pull Action Items table from Key Result into the Check-in
	frappe.model.with_doc('OKR Key Result', frm.doc.key_result, function() {
		const kr_doc = frappe.model.get_doc('OKR Key Result', frm.doc.key_result);
		frm.clear_table('action_items');
		if (kr_doc && kr_doc.action_items) {
			kr_doc.action_items.forEach(item => {
				let row = frm.add_child('action_items');
				row.action_item_title = item.action_item_title;
				row.owner_user = item.owner_user;
				row.status = item.status;
				row.progress = item.progress;
				row.due_date = item.due_date;
				row.notes = item.notes;
			});
		}
		frm.refresh_field('action_items');
	});
}

function calculate_checkin_progress_preview(frm) {
	if (!frm.doc.key_result) return;
	if (frm.doc.key_result && (!frm.custom_kr_data || frm.custom_kr_data.name !== frm.doc.key_result)) {
		frappe.db.get_value('OKR Key Result', frm.doc.key_result, ['baseline_value', 'target_value', 'metric_direction', 'unit_of_measure']).then(r => {
			frm.custom_kr_data = r.message || {};
			frm.custom_kr_data.name = frm.doc.key_result;
			do_calc();
		});
	} else {
		do_calc();
	}

	function do_calc() {
		const baseline = flt(frm.custom_kr_data.baseline_value || 0);
		const target = flt(frm.custom_kr_data.target_value || 0);
		const current = flt(frm.doc.current_value || 0);
		const direction = frm.custom_kr_data.metric_direction || 'Increase';
		const unit = frm.custom_kr_data.unit_of_measure || '';

		let progress = 0;
		if (target !== baseline) {
			if (direction === 'Decrease') {
				progress = ((baseline - current) / (baseline - target)) * 100;
			} else {
				progress = ((current - baseline) / (target - baseline)) * 100;
			}
			progress = Math.max(0, Math.min(100, progress));
		}
		frm.set_value('progress', progress);
		frm.set_df_property(
			'current_value',
			'description',
			__('Target: {0} {1} | Baseline: {2} {1} | Direction: {3} | Calculated Progress: {4}%', [target, unit, baseline, direction, progress.toFixed(1)])
		);
		render_summary_widget(frm);
	}
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

function render_summary_widget(frm) {
	const $sidebar = frm.get_field('summary_sidebar_section') ? frm.get_field('summary_sidebar_section').$wrapper : null;
	if (!$sidebar) return;

	let $widget = $sidebar.find('.okr-custom-sidebar-widget');
	if (!$widget.length) {
		$widget = $('<div class="okr-custom-sidebar-widget"></div>').prependTo($sidebar);
	}

	const progress = flt(frm.doc.progress || frm.doc.progress_percent || 0);
	const status = frm.doc.status || 'Draft';

	let status_class = 'okr-status-draft';
	if (status === 'Submitted') status_class = 'okr-status-atrisk';
	else if (status === 'Reviewed') status_class = 'okr-status-active';
	else if (status === 'Final') status_class = 'okr-status-completed';

	$widget.html(`
		<div class="okr-summary-widget">
			<div class="okr-summary-value">${progress.toFixed(1)}%</div>
			<div class="okr-summary-label">${__('Calculated Progress')}</div>
		</div>
		<div style="text-align:center;margin-bottom:16px;">
			<span class="okr-status-badge ${status_class}">${__(status)}</span>
		</div>
	`);
}
