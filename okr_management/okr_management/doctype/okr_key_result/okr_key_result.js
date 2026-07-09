frappe.ui.form.on('OKR Key Result', {
	refresh(frm) {
		if (frappe.kr_needs_reload) {
			frappe.kr_needs_reload = false;
			frm.reload_doc();
			return;
		}
		apply_key_result_ui(frm);
		fetch_and_cache_parent_plan_title(frm);
		render_action_items_list(frm);
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

frappe.ui.form.on('OKR Action Item Row', {
	open_action_item(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row && row.action_item_id) {
			frappe.set_route('Form', 'OKR Action Item', row.action_item_id);
		}
	},
	check_in(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		open_action_item_checkin(frm, row);
	},
	save_row(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (row && row.action_item_id) {
			frappe.call({
				method: 'frappe.client.set_value',
				args: {
					doctype: 'OKR Action Item',
					name: row.action_item_id,
					fieldname: {
						progress: flt(row.progress),
						status: row.status,
						priority: row.priority
					}
				},
				callback: function(r) {
					if (!r.exc) {
						frappe.show_alert({
							message: __('Action Item saved and progress updated successfully'),
							indicator: 'green'
						});
						// Close the row edit popover/dialog
						if (frm.fields_dict.action_items && frm.fields_dict.action_items.grid) {
							frm.fields_dict.action_items.grid.grid_rows.forEach(gr => {
								if (gr.doc.name === row.name) {
									gr.toggle_view(false);
								}
							});
						}
						// Reload the parent OKR Key Result
						frm.reload_doc();
					}
				}
			});
		}
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

	const has_action_items = cint(frm.doc.action_item_count || 0) > 0;
	frm.set_df_property('current_value', 'read_only', has_action_items || frm.doc.calculation_mode !== 'Manual');
	frm.toggle_display('currency', frm.doc.metric_type === 'Currency');

	const metric_type = frm.doc.metric_type;
	frm.toggle_reqd('target_value', ['Percentage', 'Boolean'].includes(metric_type));

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

function render_action_items_list(frm) {
	frm.set_df_property('action_items', 'hidden', 1);
	frm.set_df_property('action_items_html', 'hidden', 0);

	if (frm.is_new()) {
		frm.clear_table('action_items');
		frm.refresh_field('action_items');
		render_action_items_panel(frm, []);
		return;
	}

	frappe.db.get_list('OKR Action Item', {
		filters: { parent_key_result: frm.doc.name },
		fields: ['name', 'action_item_title', 'owner_user', 'status', 'progress', 'due_date', 'priority'],
		order_by: 'creation asc',
		limit: 100
	}).then(items => {
		frm.clear_table('action_items');
		(items || []).forEach(item => {
			const row = frm.add_child('action_items');
			row.action_item_id = item.name;
			row.action_item_title = item.action_item_title;
			row.owner_user = item.owner_user;
			row.priority = item.priority;
			row.status = item.status;
			row.progress = item.progress;
			row.due_date = item.due_date;
		});
		frm.doc.action_item_count = (items || []).length;
		frm.set_df_property('current_value', 'read_only', (items || []).length > 0 || frm.doc.calculation_mode !== 'Manual');
		frm.refresh_field('action_items');
		render_action_items_panel(frm, items || []);
	});
}

function render_action_items_panel(frm, items) {
	const field = frm.fields_dict.action_items_html;
	if (!field) return;

	const rows = (items || []).map((item, index) => render_action_item_row(item, index)).join('') || render_empty_action_item_row();
	field.$wrapper.html(`
		<div class="okr-kr-action-card">
			<div class="okr-kr-action-card-head">
				<h3>${__('Action Items')}</h3>
				<button type="button" class="btn btn-sm okr-black-btn okr-add-action-item">+ ${__('New Action Item')}</button>
			</div>
			<div class="okr-kr-action-table-wrap">
				<table class="okr-kr-action-table">
					<thead><tr>
						<th class="okr-check-col"><input type="checkbox" disabled></th>
						<th class="okr-num-col">${__('No.')}</th>
						<th>${__('Action Item')}</th>
						<th>${__('Owner')}</th>
						<th>${__('Status')}</th>
						<th>${__('Progress %')}</th>
						<th>${__('Check-In')}</th>
						<th class="okr-edit-col"></th>
					</tr></thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
			<div class="okr-inline-checkin-host"></div>
		</div>
	`);

	bind_action_items_panel_events(frm, items || []);
}

function render_action_item_row(item, index) {
	const progress = flt(item.progress || 0);
	return `
		<tr data-action-item="${frappe.utils.escape_html(item.name)}">
			<td class="okr-check-col"><input type="checkbox"></td>
			<td class="okr-num-col">${index + 1}</td>
			<td class="okr-action-title">${frappe.utils.escape_html(item.action_item_title || '')}</td>
			<td>${render_owner(item.owner_user)}</td>
			<td>${render_status_pill(item.status)}</td>
			<td>${render_progress_cell(progress)}</td>
			<td><button type="button" class="btn btn-xs okr-black-btn okr-inline-checkin" data-action-item="${frappe.utils.escape_html(item.name)}">${__('Check-In')}</button></td>
			<td class="okr-edit-col"><button type="button" class="btn btn-xs btn-link okr-open-action-item" data-action-item="${frappe.utils.escape_html(item.name)}">${frappe.utils.icon('edit', 'sm')}</button></td>
		</tr>
	`;
}

function render_empty_action_item_row() {
	return `<tr><td colspan="8" class="okr-empty-row">${__('No Action Items')}</td></tr>`;
}

function render_owner(owner) {
	if (!owner) return '';
	return `<span class="okr-owner-badge">${frappe.utils.escape_html(owner.charAt(0).toUpperCase())}</span><span>${frappe.utils.escape_html(owner)}</span>`;
}

function render_status_pill(status) {
	return `<span class="okr-status-mini">${frappe.utils.escape_html(status || 'Open')}</span>`;
}

function render_progress_cell(progress) {
	return `<div class="okr-progress-cell"><strong>${progress.toFixed(2)}%</strong><div class="okr-progress-track"><span style="width:${Math.max(0, Math.min(100, progress))}%"></span></div></div>`;
}

function bind_action_items_panel_events(frm, items) {
	const wrapper = frm.fields_dict.action_items_html.$wrapper;
	wrapper.off('click.okr_actions');
	wrapper.on('click.okr_actions', '.okr-add-action-item', () => open_new_action_item(frm));
	wrapper.on('click.okr_actions', '.okr-open-action-item', function() {
		const name = $(this).attr('data-action-item');
		if (name) frappe.set_route('Form', 'OKR Action Item', name);
	});
	wrapper.on('click.okr_actions', '.okr-inline-checkin', function() {
		const name = $(this).attr('data-action-item');
		const item = (items || []).find(row => row.name === name);
		render_inline_checkin_panel(frm, item);
	});
	wrapper.on('click.okr_actions', '.okr-close-checkin', () => wrapper.find('.okr-inline-checkin-host').empty());
	wrapper.on('click.okr_actions', '.okr-upload-checkin-file', () => open_checkin_file_uploader(wrapper));
	wrapper.on('click.okr_actions', '.okr-clear-checkin-file', () => {
		wrapper.find('.okr-checkin-file-url').val('');
		wrapper.find('.okr-attachment-preview').empty();
	});
	wrapper.on('click.okr_actions', '.okr-save-inline-checkin', () => save_inline_checkin(frm, wrapper));
}

function render_inline_checkin_panel(frm, item) {
	if (!item) return;
	const wrapper = frm.fields_dict.action_items_html.$wrapper;
	const progress = flt(item.progress || 0).toFixed(2);
	wrapper.find('.okr-inline-checkin-host').html(`
		<div class="okr-inline-checkin-panel" data-action-item="${frappe.utils.escape_html(item.name)}">
			<div class="okr-inline-checkin-head">
				<h3>${__('Check-In for Action Item')}: <a>${frappe.utils.escape_html(item.action_item_title || item.name)}</a></h3>
				<button type="button" class="btn btn-xs btn-link okr-close-checkin">${frappe.utils.icon('close', 'md')}</button>
			</div>
			<div class="okr-inline-checkin-body">
				<div class="okr-checkin-context">
					<h4>${__('Context (Read Only)')}</h4>
					${render_context_pair('target', 'Key Result', frm.doc.name)}
					${render_context_pair('flag', 'Objective', frm.doc.objective_title || frm.doc.objective)}
					${render_context_pair('folder-normal', 'Parent Plan', frm.doc.parent_plan)}
					${render_context_pair('calendar', 'Parent Sprint', frm.doc.parent_sprint)}
					${render_context_pair('organization', 'Company', frm.doc.company)}
					${render_context_pair('users', 'Department', frm.doc.department)}
					${render_context_pair('calendar', 'Check-In Date', frappe.datetime.str_to_user(frappe.datetime.get_today()))}
					${render_context_pair('user', 'Reported By', frappe.session.user)}
				</div>
				<div class="okr-checkin-fields">
					<div class="okr-field-row"><label>${__('Progress (%)')} <span class="text-danger">*</span></label><input type="number" min="0" max="100" step="0.01" class="form-control okr-checkin-progress" value="${progress}"></div>
					<div class="okr-field-row">
						<label>${__('Status')}</label>
						<select class="form-control okr-checkin-status">
							<option value="In Progress" ${item.status === 'In Progress' ? 'selected' : ''}>${__('In Progress')}</option>
							<option value="Blocked" ${item.status === 'Blocked' ? 'selected' : ''}>${__('Blocked')}</option>
							<option value="On Hold" ${item.status === 'On Hold' ? 'selected' : ''}>${__('On Hold')}</option>
							<option value="Open" ${item.status === 'Open' ? 'selected' : ''}>${__('Open')}</option>
						</select>
					</div>
					<div class="okr-field-row"><label>${__('What work was completed?')} <span class="text-danger">*</span></label><textarea class="form-control okr-checkin-update" rows="3"></textarea></div>
					<div class="okr-field-row"><label>${__('Blockers (What is preventing progress?)')}</label><textarea class="form-control okr-checkin-blocker" rows="2"></textarea></div>
					<div class="okr-field-row"><label>${__('Any cross-team/person dependency?')}</label><textarea class="form-control okr-checkin-dependency" rows="2"></textarea></div>
					<div class="okr-field-row okr-attachment-row"><label>${__('Attachment')}</label><input type="hidden" class="okr-checkin-file-url"><div class="okr-attachment-preview"></div><button type="button" class="btn btn-sm btn-default okr-upload-checkin-file">${frappe.utils.icon('attachment', 'sm')} ${__('Attach File')}</button><div class="small text-muted">${__('You can upload images, PDFs, Excel, etc.')}</div></div>
				</div>
			</div>
			<div class="okr-inline-checkin-actions"><button type="button" class="btn btn-default okr-close-checkin">${__('Cancel')}</button><button type="button" class="btn okr-black-btn okr-save-inline-checkin">${__('Save Check-In')}</button></div>
		</div>
	`);
	frappe.utils.scroll_to(wrapper.find('.okr-inline-checkin-panel'), true, 20);
}

function render_context_pair(icon, label, value) {
	return `<div class="okr-context-pair"><span class="okr-context-icon">${frappe.utils.icon(icon, 'sm')}</span><div><strong>${__(label)}</strong><span>${frappe.utils.escape_html(value || '-')}</span></div></div>`;
}

function open_checkin_file_uploader(wrapper) {
	new frappe.ui.FileUploader({
		doctype: 'OKR Check In',
		on_success(file) {
			const url = file.file_url || file.file_url_private || '';
			wrapper.find('.okr-checkin-file-url').val(url);
			wrapper.find('.okr-attachment-preview').html(`<div class="okr-file-chip"><span>${frappe.utils.escape_html(file.file_name || url)}</span><button type="button" class="btn btn-xs btn-link okr-clear-checkin-file">${frappe.utils.icon('close', 'sm')}</button></div>`);
		}
	});
}

function save_inline_checkin(frm, wrapper) {
	const panel = wrapper.find('.okr-inline-checkin-panel');
	const action_item = panel.attr('data-action-item');
	const progress = flt(panel.find('.okr-checkin-progress').val());
	const checkin_status = panel.find('.okr-checkin-status').val();
	const achievements = (panel.find('.okr-checkin-update').val() || '').trim();
	if (!achievements) {
		frappe.msgprint(__('Please enter what work was completed.'));
		return;
	}
	const item = (frm.doc.action_items || []).find(row => row.action_item_id === action_item) || {};
	frappe.call({
		method: 'frappe.client.insert',
		args: { doc: {
			doctype: 'OKR Check In', key_result: frm.doc.name, action_item: action_item,
			progress: progress, current_value: progress, achievements: achievements,
			blockers: panel.find('.okr-checkin-blocker').val() || '',
			dependency_description: panel.find('.okr-checkin-dependency').val() || '',
			attachment: panel.find('.okr-checkin-file-url').val() || '',
			reported_by: frappe.session.user, checkin_date: frappe.datetime.get_today(),
			parent_plan: frm.doc.parent_plan, parent_sprint: frm.doc.parent_sprint,
			company: frm.doc.company, department: frm.doc.department, financial_year: frm.doc.financial_year,
			action_items: [
				{
					action_item_id: action_item,
					action_item_title: item.action_item_title || '',
					owner_user: item.owner_user || frappe.session.user,
					priority: item.priority || 'Medium',
					status: progress >= 100 ? 'Completed' : checkin_status,
					progress: progress,
					due_date: item.due_date,
					notes: achievements
				}
			]
		} },
		freeze: true,
		freeze_message: __('Saving Check-In...'),
		callback(r) {
			if (!r.exc) {
				frappe.show_alert({ message: __('Check-In saved'), indicator: 'green' });
				frm.reload_doc();
			}
		}
	});
}

function open_action_item_checkin(frm, row) {
if (!row || !row.action_item_id) {
return;
}

frappe.kr_needs_reload = true;
frappe.okr_checkin_action_item = row.action_item_id;
frappe.new_doc("OKR Check In", get_checkin_context(frm, row));
}

function get_action_item_context(frm) {
	return {
		parent_key_result: frm.doc.name,
		parent_objective: frm.doc.objective,
		parent_sprint: frm.doc.parent_sprint,
		parent_plan: frm.doc.parent_plan,
		company: frm.doc.company,
		department: frm.doc.department,
		financial_year: frm.doc.financial_year,
		owner_user: frappe.session.user
	};
}

function open_new_action_item(frm) {
	frappe.kr_needs_reload = true;
	frappe.new_doc('OKR Action Item', get_action_item_context(frm));
}

function get_checkin_context(frm, row) {
	return {
		key_result: frm.doc.name,
		action_item: row.action_item_id,
		parent_plan: frm.doc.parent_plan,
		parent_sprint: frm.doc.parent_sprint,
		company: frm.doc.company,
		department: frm.doc.department,
		financial_year: frm.doc.financial_year,
		reported_by: frappe.session.user,
		progress: row.progress || 0,
		current_value: row.progress || 0
	};
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



