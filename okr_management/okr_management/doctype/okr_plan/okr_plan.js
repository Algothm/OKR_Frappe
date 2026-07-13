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
	},
	status(frm) {
		apply_plan_locks(frm);
	},
	onload_post_render(frm) {
		style_add_member_button(frm);
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
		}
	}
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

	['financial_year', 'company', 'owner_user'].forEach((fieldname) => {
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
