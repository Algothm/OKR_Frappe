frappe.ui.form.on('OKR Plan', {
	refresh(frm) {
		frm.set_df_property('naming_series', 'hidden', 1);
		if (!frm.doc.company) {
			frm.set_value('company', frappe.defaults.get_user_default('Company') || '');
		}
		if (!frm.doc.owner_user) {
			frm.set_value('owner_user', frappe.session.user);
		}
		if (frm.doc.owner_user && (!frm.doc.members || frm.doc.members.length === 0)) {
			frm.add_child('members', {
				member_user: frm.doc.owner_user,
				role: 'Admin'
			});
			frm.refresh_field('members');
		}
		apply_plan_locks(frm);
		style_add_member_button(frm);
		configure_period_selection(frm, false);
		update_sprint_timeline(frm);
	},
	status(frm) {
		apply_plan_locks(frm);
	},
	financial_year(frm) {
		update_sprint_timeline(frm);
	},
	sprint_frequency(frm) {
		configure_period_selection(frm, true);
		update_sprint_timeline(frm);
	},
	period_selection(frm) {
		update_sprint_timeline(frm);
	},
	custom_start_date(frm) {
		update_sprint_timeline(frm);
	},
	custom_end_date(frm) {
		update_sprint_timeline(frm);
	},
	onload_post_render(frm) {
		style_add_member_button(frm);
		update_sprint_timeline(frm);
	},
	members_add(frm) {
		style_add_member_button(frm);
	},
	members_remove(frm) {
		style_add_member_button(frm);
	},
	members_on_form_rendered(frm, cdt, cdn) {
		customize_row_editor(frm, cdt, cdn);
	}
});

var okr_plan_sprint_months = [
	'January', 'February', 'March', 'April', 'May', 'June',
	'July', 'August', 'September', 'October', 'November', 'December'
];
var okr_plan_sprint_quarters = ['Q1', 'Q2', 'Q3', 'Q4'];

function configure_period_selection(frm, reset_value) {
	const is_custom = frm.doc.sprint_frequency === 'Custom';
	const is_monthly = frm.doc.sprint_frequency === 'Monthly';
	const options = is_monthly ? okr_plan_sprint_months : okr_plan_sprint_quarters;

	frm.set_df_property('period_selection', 'options', options.join('\n'));
	frm.set_df_property('period_selection', 'label', is_monthly ? __('Month') : __('Quarter'));
	frm.toggle_display('period_selection', !is_custom);
	frm.toggle_reqd('period_selection', !is_custom);
	frm.toggle_display('custom_start_date', is_custom);
	frm.toggle_display('custom_end_date', is_custom);
	frm.toggle_display('sprint_timeline_preview', !is_custom);
	frm.toggle_display('sprint_config_col_4', is_custom);
	frm.toggle_display('custom_timeline_preview', is_custom);
	frm.toggle_reqd('custom_start_date', is_custom);
	frm.toggle_reqd('custom_end_date', is_custom);
	apply_sprint_configuration_layout(frm);
	setTimeout(() => apply_sprint_configuration_layout(frm), 50);

	if (!reset_value) {
		if (!is_custom && !options.includes(frm.doc.period_selection)) {
			frm.set_value('period_selection', options[0]);
		}
		return;
	}
	if (is_custom) {
		frm.set_value('period_selection', '');
	} else {
		frm.set_value('period_selection', options[0]);
		frm.set_value('custom_start_date', '');
		frm.set_value('custom_end_date', '');
	}
}

function apply_sprint_configuration_layout(frm) {
	const is_custom = frm.doc.sprint_frequency === 'Custom';
	const column_for = (fieldname) => {
		const field = frm.fields_dict[fieldname];
		return field && field.$wrapper ? field.$wrapper.closest('.form-column') : $();
	};
	const columns = [
		column_for('sprint_frequency'),
		column_for(is_custom ? 'custom_start_date' : 'period_selection'),
		column_for(is_custom ? 'custom_end_date' : 'sprint_timeline_preview'),
		column_for('custom_timeline_preview')
	];
	const active_columns = is_custom ? columns : columns.slice(0, 3);
	const unique_columns = [];

	columns.forEach(($column) => {
		if ($column.length && !unique_columns.some(($item) => $item[0] === $column[0])) {
			unique_columns.push($column);
		}
	});
	unique_columns.forEach(($column) => $column.hide());
	active_columns.forEach(($column) => {
		if (!$column.length) return;
		const element = $column[0];
		element.style.setProperty('display', 'block', 'important');
		element.style.setProperty('flex', '1 1 220px', 'important');
		element.style.setProperty('width', 'auto', 'important');
		element.style.setProperty('max-width', 'none', 'important');
		element.style.setProperty('min-width', '220px');
	});
	if (active_columns[0] && active_columns[0].length) {
		active_columns[0].parent().css({ display: 'flex', 'flex-wrap': 'wrap' });
	}
}

function update_sprint_timeline(frm) {
	if (!frm.doc.financial_year) {
		render_timeline_placeholder(frm, __('Select Financial Year to calculate the Sprint Timeline.'));
		return;
	}
	if (frm.doc.sprint_frequency === 'Custom') {
		render_custom_timeline(frm);
		return;
	}
	if (!frm.doc.period_selection) {
		const options = frm.doc.sprint_frequency === 'Monthly'
			? okr_plan_sprint_months : okr_plan_sprint_quarters;
		frm.set_value('period_selection', options[0]);
		return;
	}

	const requested_year = frm.doc.financial_year;
	const requested_frequency = frm.doc.sprint_frequency;
	const requested_period = frm.doc.period_selection;
	frappe.db.get_value('Fiscal Year', requested_year, ['year_start_date', 'year_end_date'])
		.then((response) => {
			if (
				frm.doc.financial_year !== requested_year
				|| frm.doc.sprint_frequency !== requested_frequency
				|| frm.doc.period_selection !== requested_period
			) return;
			const fiscal_year = response.message || {};
			if (!fiscal_year.year_start_date || !fiscal_year.year_end_date) {
				render_timeline_placeholder(frm, __('The selected Financial Year has no date range.'));
				return;
			}
			if (requested_frequency === 'Quarterly') {
				const quarter_index = okr_plan_sprint_quarters.indexOf(requested_period);
				if (quarter_index < 0) return;
				const start = moment(fiscal_year.year_start_date).add(quarter_index * 3, 'months');
				const end = moment.min(start.clone().add(3, 'months').subtract(1, 'day'), moment(fiscal_year.year_end_date));
				render_timeline(frm, start, end);
				return;
			}
			const month_index = okr_plan_sprint_months.indexOf(requested_period);
			if (month_index < 0) return;
			const fiscal_start = moment(fiscal_year.year_start_date);
			const calendar_year = month_index >= fiscal_start.month()
				? fiscal_start.year() : fiscal_start.year() + 1;
			const start = moment([calendar_year, month_index, 1]);
			const end = moment.min(start.clone().endOf('month'), moment(fiscal_year.year_end_date));
			render_timeline(frm, start, end);
		});
}

function render_custom_timeline(frm) {
	if (!frm.doc.custom_start_date || !frm.doc.custom_end_date) {
		render_timeline_placeholder(frm, __('Select Start Date and End Date to preview the timeline.'));
		return;
	}
	const start = moment(frm.doc.custom_start_date);
	const end = moment(frm.doc.custom_end_date);
	if (!start.isValid() || !end.isValid() || end.isBefore(start, 'day')) {
		render_timeline_placeholder(frm, __('End Date must be on or after Start Date.'), true);
		return;
	}
	render_timeline(frm, start, end);
}

function render_timeline(frm, start, end) {
	const days = end.diff(start, 'days') + 1;
	const date_range = start.format('DD-MMM-YYYY')
		+ ' <span aria-hidden="true">&rarr;</span> '
		+ end.format('DD-MMM-YYYY');
	render_timeline_card(frm, date_range, __('{0} Days', [days]), false);
}

function render_timeline_placeholder(frm, message, is_error = false) {
	render_timeline_card(frm, message, '', is_error);
}

function render_timeline_card(frm, primary_text, secondary_text, is_error) {
	const fieldname = frm.doc.sprint_frequency === 'Custom'
		? 'custom_timeline_preview' : 'sprint_timeline_preview';
	const field = frm.fields_dict[fieldname];
	if (!field || !field.$wrapper) return;
	const secondary_color = is_error ? 'var(--red-600)' : 'var(--text-muted)';
	const content = secondary_text
		? '<div style="font-size:13px;font-weight:600;color:var(--text-color);'
			+ 'line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
			+ primary_text + ' <span style="color:var(--text-muted);">&bull;</span> '
			+ '<span style="font-weight:500;color:' + secondary_color + ';">'
			+ secondary_text + '</span></div>'
		: '<div style="font-size:13px;font-weight:500;color:'
			+ secondary_color + ';line-height:1.2;white-space:nowrap;overflow:hidden;'
			+ 'text-overflow:ellipsis;">' + primary_text + '</div>';
	field.$wrapper.html(
		'<div class="form-group">'
		+ '<div class="control-label">' + __('Timeline Preview') + '</div>'
		+ '<div class="like-disabled-input" style="height:var(--input-height);'
		+ 'min-height:var(--input-height);padding:6px 12px;display:flex;'
		+ 'align-items:center;border-radius:var(--border-radius);overflow:hidden;">'
		+ content
		+ '</div></div>'
	);
}

function style_add_member_button(frm) {
	let grid = frm.fields_dict['members'] && frm.fields_dict['members'].grid;
	if (grid && grid.wrapper) {
		let $btn = grid.wrapper.find('.grid-add-row');
		if ($btn.length > 0) {
			$btn.removeClass('btn-secondary btn-default btn-xs btn-sm').addClass('btn-primary btn-sm');
			const expected_text = __('Add Member');
			if (!$btn.text().includes(expected_text)) {
				let icon_html = "";
				if (frappe.utils && typeof frappe.utils.icon === 'function') {
					icon_html = frappe.utils.icon('add', 'xs') + ' ';
				} else {
					icon_html = '<i class="fa fa-plus"></i> ';
				}
				$btn.html(icon_html + expected_text);
			}
			$btn.off('click').on('click.okr-plan-add-member', (event) => {
				event.preventDefault();
				event.stopImmediatePropagation();
				open_add_member_dialog(frm);
			});
		}
	}
}

function open_add_member_dialog(frm) {
	const role_options = (
		frappe.meta.get_docfield('OKR Plan Team Member', 'role', frm.doc.name).options
		|| 'Admin'
	).split('\n');
	const dialog = new frappe.ui.Dialog({
		title: __('Add Member'),
		fields: [
			{
				fieldname: 'member_user',
				fieldtype: 'Link',
				label: __('User'),
				options: 'User',
				reqd: 1
			},
			{
				fieldname: 'role',
				fieldtype: 'Select',
				label: __('Role'),
				options: role_options.join('\n'),
				default: role_options[0],
				reqd: 1
			}
		],
		primary_action_label: __('Save'),
		primary_action(values) {
			const already_added = (frm.doc.members || []).some(
				(member) => member.member_user === values.member_user
			);
			if (already_added) {
				frappe.msgprint(__('User {0} is already a Plan Team member.', [values.member_user]));
				return;
			}
			frm.add_child('members', {
				member_user: values.member_user,
				role: values.role
			});
			frm.refresh_field('members');
			frm.dirty();
			dialog.hide();
		}
	});
	dialog.show();
}

function customize_row_editor(frm, cdt, cdn) {
	let grid = frm.fields_dict['members'] && frm.fields_dict['members'].grid;
	if (!grid || !grid.wrapper) return;

	const apply_customization = () => {
		let $row_editor = grid.wrapper.find('.grid-row-open');
		if ($row_editor.length > 0) {
			// Hide unnecessary buttons in the top toolbar
			$row_editor.find('.grid-insert-row-below, .grid-insert-row, .grid-duplicate-row, .grid-move-row, .grid-collapse-row').hide();
			
			// Customize bottom-right button
			let $bottom_btn = $row_editor.find('.grid-append-row');
			if ($bottom_btn.length > 0) {
				$bottom_btn.text(__('Save'))
					.removeClass('btn-secondary btn-default')
					.addClass('btn-primary')
					.off('click')
					.on('click', function(e) {
						e.preventDefault();
						e.stopImmediatePropagation();
						let $collapse_btn = $row_editor.find('.grid-collapse-row');
						if ($collapse_btn.length > 0) {
							$collapse_btn.click();
						}
					});
			}
		}
	};

	apply_customization();
	setTimeout(apply_customization, 50);
	setTimeout(apply_customization, 200);
}



function apply_plan_locks(frm) {
	const is_draft = !frm.doc.status || frm.doc.status === 'Draft';
	const is_closed = frm.doc.status === 'Archived';
	const can_manage_status = frm.perm && frm.perm[0] && frm.perm[0].write
		&& (frappe.user.has_role('System Manager') || frappe.user.has_role('OKR Admin') || frappe.session.user === 'Administrator');

	[
		'financial_year', 'company', 'owner_user', 'sprint_frequency',
		'period_selection', 'custom_start_date', 'custom_end_date'
	].forEach((fieldname) => {
		frm.set_df_property(fieldname, 'read_only', !is_draft);
	});
	frm.set_df_property('description', 'read_only', is_closed);
	frm.set_df_property('progress', 'hidden', 1);

	if (!frm.doc.status) {
		frm.set_value('status', 'Draft');
	}
	frm.set_df_property('status', 'hidden', 0);
	frm.set_df_property('status', 'read_only', !can_manage_status);
}
