frappe.ui.form.on('OKR Action Item', {
	onload(frm) {
		apply_route_context(frm);
	},
	refresh(frm) {
		apply_action_item_ui(frm);

		if (frm.is_new()) {
			apply_route_context(frm);
			if (frm.doc.parent_key_result && !frm.doc.parent_objective) {
				fetch_parent_key_result_context(frm);
			}
		}

		if (frm.is_new() && !frm.doc.due_date) {
			frm.set_value('due_date', frappe.datetime.get_today());
		}

		if (frm.doc.action_item_title && !frm.is_new()) {
			frm.page.set_title(frm.doc.action_item_title);
		}
	},
	status(frm) {
		apply_action_item_ui(frm);
	},
	priority(frm) {
	},
	parent_key_result(frm) {
		fetch_parent_key_result_context(frm);
	},
	open_action_item(frm, cdt, cdn) {
		const child = frappe.get_doc(cdt, cdn);
		if (child && child.name) {
			frappe.set_route('Form', 'OKR Action Item', child.name);
		}
	},
	check_in(frm) {
		if (frm.doc.parent_key_result && !frm.is_new()) {
			frappe.kr_needs_reload = true;
			frappe.okr_checkin_action_item = frm.doc.name;
			frappe.new_doc('OKR Check In', {
				key_result: frm.doc.parent_key_result,
				action_item: frm.doc.name,
				parent_plan: frm.doc.parent_plan,
				parent_sprint: frm.doc.parent_sprint,
				company: frm.doc.company,
				department: frm.doc.department,
				financial_year: frm.doc.financial_year,
				reported_by: frappe.session.user
			});
		}
	},
	after_save(frm) {
		if (frm.doc.parent_key_result) {
			frappe.kr_needs_reload = true;
			frappe.set_route('Form', 'OKR Key Result', frm.doc.parent_key_result);
		}
	}
});

function apply_route_context(frm) {
	if (!frm.is_new() || !frappe.route_options) {
		return;
	}

	const route_options = frappe.route_options;
	if (!route_options.parent_key_result && route_options.parenttype === 'OKR Key Result' && route_options.parent) {
		route_options.parent_key_result = route_options.parent;
	}

	Object.keys(route_options).forEach(key => {
		const value = route_options[key];
		if (value !== undefined && value !== null && value !== '' && frm.fields_dict[key]) {
			frm.set_value(key, value);
		}
	});

	if (route_options.parent_key_result) {
		frm.set_value('parent_key_result', route_options.parent_key_result).then(() => {
			fetch_parent_key_result_context(frm);
		});
		frappe.route_options = null;
	}
}

function apply_action_item_ui(frm) {
	const readonly_fields = [
		'parent_objective', 'parent_sprint', 'parent_plan',
		'company', 'department', 'financial_year', 'due_date'
	];
	readonly_fields.forEach(fieldname => {
		frm.set_df_property(fieldname, 'read_only', 1);
	});
}

function fetch_parent_key_result_context(frm) {
	if (!frm.doc.parent_key_result) {
		const fields = ['parent_objective', 'parent_sprint', 'parent_plan', 'company', 'department', 'financial_year', 'reviewer'];
		fields.forEach(f => frm.set_value(f, ''));
		return;
	}

	frappe.db.get_value('OKR Key Result', frm.doc.parent_key_result, [
		'objective', 'parent_sprint', 'parent_plan', 'company', 'department', 'financial_year', 'reviewer'
	]).then(r => {
		const kr = r.message || {};
		frm.set_value('parent_objective', kr.objective || '');
		frm.set_value('parent_sprint', kr.parent_sprint || '');
		frm.set_value('parent_plan', kr.parent_plan || '');
		frm.set_value('company', kr.company || '');
		frm.set_value('department', kr.department || '');
		frm.set_value('financial_year', kr.financial_year || '');
		if (!frm.doc.reviewer) {
			frm.set_value('reviewer', kr.reviewer || '');
		}
	});
}


