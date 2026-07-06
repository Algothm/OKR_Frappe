frappe.ui.form.on('OKR Action Item', {
	form_render(frm, cdt, cdn) {
		apply_action_item_ui(frm, cdt, cdn);
	},
	status(frm, cdt, cdn) {
		apply_action_item_ui(frm, cdt, cdn);
	},
	action_items_add(frm, cdt, cdn) {
		apply_action_item_ui(frm, cdt, cdn);
	}
});

function apply_action_item_ui(frm, cdt, cdn) {
	let child = frappe.get_doc(cdt, cdn);
	if (!child) return;
	
	let parent_closed = ['Closed', 'Archived'].includes(frm.doc.status);
	let child_completed = child.status === 'Completed';
	let child_locked = ['Closed', 'Archived'].includes(child.status);

	const always_readonly = [
		'parent_key_result', 'parent_objective', 'parent_sprint', 'parent_plan',
		'company', 'department', 'completion_date'
	];
	always_readonly.forEach(fieldname => {
		frappe.model.set_df_property(cdt, cdn, fieldname, 'read_only', 1);
	});

	if (parent_closed || child_locked) {
		const all_fields = [
			'action_item_title', 'description', 'owner_user', 'start_date', 'due_date',
			'priority', 'weight', 'progress', 'notes', 'status'
		];
		all_fields.forEach(fieldname => {
			frappe.model.set_df_property(cdt, cdn, fieldname, 'read_only', 1);
		});
	} else if (child_completed) {
		const config_fields = [
			'action_item_title', 'description', 'owner_user', 'start_date', 'due_date',
			'priority', 'weight', 'progress'
		];
		config_fields.forEach(fieldname => {
			frappe.model.set_df_property(cdt, cdn, fieldname, 'read_only', 1);
		});
		frappe.model.set_df_property(cdt, cdn, 'notes', 'read_only', 0);
		frappe.model.set_df_property(cdt, cdn, 'status', 'read_only', 0);
	} else {
		const editable_fields = [
			'action_item_title', 'description', 'owner_user', 'start_date', 'due_date',
			'priority', 'weight', 'progress', 'notes', 'status'
		];
		editable_fields.forEach(fieldname => {
			frappe.model.set_df_property(cdt, cdn, fieldname, 'read_only', 0);
		});
	}
}
