frappe.ui.form.on('OKR Action Item', {
    setup(frm) {
        const employee_meta = frappe.get_meta('Employee');
        if (employee_meta) employee_meta.show_title_field_in_link = 1;

        frm.set_query('assigned_to', () => ({ filters: { status: 'Active' } }));
        const assigned_to_field = frappe.meta.get_docfield('OKR Action Item', 'assigned_to', frm.doc.name);
        if (assigned_to_field) {
            assigned_to_field.only_select = 1;
            assigned_to_field.show_title_field_in_link = 1;
        }

        const key_result_field = frappe.meta.get_docfield('OKR Action Item', 'parent_key_result', frm.doc.name);
        if (key_result_field) key_result_field.only_select = 1;
    },
    onload(frm) {
        apply_route_context(frm);
    },
    refresh(frm) {
        apply_action_item_ui(frm);
        apply_route_context(frm);
        if (frm.doc.parent_key_result) fetch_parent_key_result_context(frm);
        else render_timeline_preview(frm);
        if (frm.doc.action_item_title && !frm.is_new()) frm.page.set_title(frm.doc.action_item_title);
    },
    parent_key_result(frm) {
        fetch_parent_key_result_context(frm);
    },
    validate(frm) {
        if (!frm.doc.assigned_to) {
            frappe.throw(__('Assigned To is required.'));
        }
    },
    open_action_item(frm, cdt, cdn) {
        const child = frappe.get_doc(cdt, cdn);
        if (child && child.name) frappe.set_route('Form', 'OKR Action Item', child.name);
    },
    check_in(frm) {
        if (frm.doc.parent_key_result && !frm.is_new()) {
            frappe.kr_needs_reload = true;
            frappe.okr_checkin_action_item = frm.doc.name;
            frappe.new_doc('OKR Check In', {
                key_result: frm.doc.parent_key_result,
                action_item: frm.doc.name,
                parent_plan: frm.doc.parent_plan,
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
    if (!frm.is_new() || !frappe.route_options) return;
    const route_options = frappe.route_options;
    if (!route_options.parent_key_result && route_options.parenttype === 'OKR Key Result' && route_options.parent) {
        route_options.parent_key_result = route_options.parent;
    }
    Object.keys(route_options).forEach((key) => {
        const value = route_options[key];
        if (value !== undefined && value !== null && value !== '' && frm.fields_dict[key]) {
            frm.set_value(key, value);
        }
    });
    if (route_options.parent_key_result) {
        frm.set_value('parent_key_result', route_options.parent_key_result)
            .then(() => fetch_parent_key_result_context(frm));
        frappe.route_options = null;
    }
}

function apply_action_item_ui(frm) {
    [
        'parent_plan', 'plan_title', 'plan_description', 'company', 'financial_year',
        'sprint_frequency', 'selected_period', 'context_start_date', 'context_end_date',
        'parent_objective', 'objective_title', 'key_result_title'
    ].forEach((fieldname) => frm.set_df_property(fieldname, 'read_only', 1));

    [
        'priority', 'status', 'due_date', 'owner_user', 'reviewer', 'department',
        'parent_plan', 'parent_objective', 'objective_title', 'key_result_title',
        'sprint_frequency', 'selected_period', 'progress_visualization_html',
        'execution_progress_section', 'execution_progress_col_break',
        'assignment_section', 'assignment_col_break_1', 'assignment_col_break_2',
        'completion_date', 'start_date', 'inherited_context_section', 'inherited_col_break'
    ].forEach((fieldname) => frm.set_df_property(fieldname, 'hidden', 1));
}

function clear_context(frm) {
    [
        'parent_plan', 'plan_title', 'plan_description', 'company', 'financial_year', 'sprint_frequency', 'selected_period',
        'context_start_date', 'context_end_date', 'parent_objective', 'objective_title', 'key_result_title'
    ].forEach((fieldname) => frm.set_value(fieldname, ''));
    render_timeline_preview(frm);
}

function fetch_parent_key_result_context(frm) {
    if (!frm.doc.parent_key_result) {
        clear_context(frm);
        return;
    }
    const selected_key_result = frm.doc.parent_key_result;
    frappe.db.get_value('OKR Key Result', selected_key_result, [
        'key_result_title', 'objective', 'parent_plan', 'company', 'department',
        'financial_year', 'start_date', 'end_date', 'reviewer', 'objective_title'
    ]).then((response) => {
        if (frm.doc.parent_key_result !== selected_key_result) return;
        const kr = response.message || {};
        frappe.utils.add_link_title('OKR Key Result', selected_key_result, kr.key_result_title || selected_key_result);
        const values = {
            parent_objective: kr.objective || '',
            objective_title: kr.objective_title || '',
            parent_plan: kr.parent_plan || '',
            company: kr.company || '',
            department: kr.department || '',
            financial_year: kr.financial_year || '',
            context_start_date: kr.start_date || '',
            context_end_date: kr.end_date || '',
            key_result_title: kr.key_result_title || ''
        };
        if (!frm.doc.reviewer) values.reviewer = kr.reviewer || '';
        return Promise.all(Object.entries(values).map(([key, value]) => frm.set_value(key, value)))
            .then(() => load_plan_context(frm, kr.parent_plan));
    });
}

function load_plan_context(frm, plan_name) {
    if (!plan_name) {
        frm.set_value('plan_title', '');
        frm.set_value('plan_description', '');
        frm.set_value('sprint_frequency', '');
        frm.set_value('selected_period', '');
        render_timeline_preview(frm);
        return;
    }
    frappe.db.get_value('OKR Plan', plan_name, ['plan_name', 'description', 'sprint_frequency', 'period_selection'])
        .then((response) => {
            if (frm.doc.parent_plan !== plan_name) return;
            const plan = response.message || {};
            if (plan.plan_name) frappe.utils.add_link_title('OKR Plan', plan_name, plan.plan_name);
            return Promise.all([
                frm.set_value('plan_title', plan.plan_name || ''),
                frm.set_value('plan_description', plan.description || ''),
                frm.set_value('sprint_frequency', plan.sprint_frequency || ''),
                frm.set_value('selected_period', plan.period_selection || __('Custom'))
            ]).then(() => render_timeline_preview(frm));
        });
}

function render_timeline_preview(frm) {
    const field = frm.fields_dict.timeline_preview;
    if (!field || !field.$wrapper) return;
    let text = __('Select a Key Result to preview its timeline.');
    let detail = '';
    if (frm.doc.context_start_date && frm.doc.context_end_date) {
        text = frappe.datetime.str_to_user(frm.doc.context_start_date)
            + ' &rarr; ' + frappe.datetime.str_to_user(frm.doc.context_end_date);
        detail = __('{0} Days', [
            frappe.datetime.get_day_diff(frm.doc.context_end_date, frm.doc.context_start_date) + 1
        ]);
    }
    field.$wrapper.html(
        '<div class="form-group"><div class="control-label">' + __('Timeline Preview')
        + '</div><div class="like-disabled-input" style="height:var(--input-height);'
        + 'min-height:var(--input-height);padding:6px 12px;display:flex;align-items:center;'
        + 'border-radius:var(--border-radius);overflow:hidden;"><div style="font-size:13px;'
        + 'font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
        + text + (detail ? ' <span style="color:var(--text-muted);">&bull; ' + detail + '</span>' : '')
        + '</div></div></div>'
    );
}
