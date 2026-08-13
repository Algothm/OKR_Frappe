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
    onload_post_render(frm) {
        if (frm.doc.parent_key_result) fetch_parent_key_result_context(frm);
        else render_context_preview(frm, {});
    },
    refresh(frm) {
        apply_action_item_ui(frm);
        apply_route_context(frm);
        if (frm.doc.parent_key_result) fetch_parent_key_result_context(frm);
        else render_context_preview(frm, {});
        if (frm.doc.action_item_title && !frm.is_new()) frm.page.set_title(frm.doc.action_item_title);
    },
    parent_key_result(frm) {
        fetch_parent_key_result_context(frm);
    },
    due_date(frm) {
        validate_due_date_against_target(frm);
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
            if (key === 'financial_year') {
                frm.doc.financial_year = value;
                frm.refresh_field('financial_year');
            } else {
                frm.set_value(key, value);
            }
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
        'sprint_frequency', 'context_start_date', 'context_end_date',
        'parent_objective', 'objective_title', 'key_result_title'
    ].forEach((fieldname) => frm.set_df_property(fieldname, 'read_only', 1));

	frm.set_df_property('context_preview_html', 'label', __('Context and Preview'));
	frm.toggle_display('context_preview_html', 1);

    [
        'action_item_setup_heading', 'progress', 'priority', 'status', 'owner_user', 'reviewer', 'department',
        'parent_plan', 'parent_objective', 'objective_title', 'key_result_title',
        'plan_title', 'plan_description', 'company', 'financial_year', 'sprint_frequency',
        'context_start_date', 'context_end_date', 'timeline_preview', 'progress_visualization_html',
        'execution_progress_section', 'execution_progress_col_break',
        'assignment_section', 'assignment_col_break_1', 'assignment_col_break_2',
        'completion_date', 'start_date', 'inherited_context_section', 'inherited_col_break'
    ].forEach((fieldname) => frm.set_df_property(fieldname, 'hidden', 1));

    if (frm.fields_dict.description && frm.fields_dict.description.$input) {
        frm.fields_dict.description.$input.css('height', '80px');
    }


    const assigned_to_field = frm.fields_dict.assigned_to;

    if (assigned_to_field && assigned_to_field.$wrapper) {
        assigned_to_field.$wrapper.css({
            'width': '100%',
            'display': 'inline-block',
            'margin-right': '4%',
            'vertical-align': 'top'
        });
    }

    if (window.okr_management && window.okr_management.ui && window.okr_management.ui.apply_context_panel_style) {
        window.okr_management.ui.apply_context_panel_style(frm);
    }
}

function clear_context(frm) {
    [
        'parent_plan', 'plan_title', 'plan_description', 'company', 'financial_year', 'sprint_frequency',
        'context_start_date', 'context_end_date', 'parent_objective', 'objective_title', 'key_result_title'
    ].forEach((fieldname) => frm.set_value(fieldname, ''));
    render_context_preview(frm);
}

function set_due_date_target_guidance(frm, target_date) {
    const message = target_date
        ? __('Key Result Target Date: {0}. Due Date must be on or before this date and inside the same target period.', [frappe.datetime.str_to_user(target_date)])
        : __('Select a Key Result to load its Target Date.');
    frm.set_df_property('due_date', 'description', message);
}

function validate_due_date_against_target(frm) {
    if (!frm.doc.due_date || !frm.doc.context_end_date) return;
    if (moment(frm.doc.due_date).isAfter(frm.doc.context_end_date)) {
        frappe.msgprint({
            title: __('Invalid Due Date'),
            message: __('Due Date cannot be after the Key Result Target Date {0}.', [frappe.datetime.str_to_user(frm.doc.context_end_date)]),
            indicator: 'red'
        });
        frm.set_value('due_date', '');
    }
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
        set_due_date_target_guidance(frm, kr.end_date);
        frappe.utils.add_link_title('OKR Key Result', selected_key_result, kr.key_result_title || selected_key_result);
        const values = {
            parent_objective: kr.objective || '',
            objective_title: kr.objective_title || '',
            parent_plan: kr.parent_plan || '',
            company: kr.company || '',
            department: kr.department || '',
            context_start_date: kr.start_date || '',
            context_end_date: kr.end_date || '',
            key_result_title: kr.key_result_title || ''
        };
        if (!frm.doc.reviewer) values.reviewer = kr.reviewer || '';
        frm.doc.financial_year = kr.financial_year || '';
        frm.refresh_field('financial_year');
        frm.set_value(values);
        load_plan_context(frm, kr.parent_plan, kr);
    });
}

function load_plan_context(frm, plan_name, kr) {
    if (!plan_name) {
        frm.set_value({
            plan_title: '',
            plan_description: '',
            sprint_frequency: '',
        });
        render_context_preview(frm, { kr });
        return;
    }
    frappe.call({
        method: 'okr_management.okr_management.doctype.okr_plan.okr_plan.get_plan_context',
        args: { plan_name }
    }).then((response) => {
        if (frm.doc.parent_plan !== plan_name) return;
        const plan = response.message || {};
        const fiscal_start = plan.start_date || '';
        const fiscal_end = plan.end_date || '';
        if (plan.plan_name) frappe.utils.add_link_title('OKR Plan', plan_name, plan.plan_name);
        frm.doc.financial_year = plan.financial_year || frm.doc.financial_year || '';
        frm.refresh_field('financial_year');
        frm.set_value({
            plan_title: plan.plan_name || '',
            plan_description: plan.description || '',
            sprint_frequency: plan.sprint_frequency || '',
        });
        render_context_preview(frm, {
            kr: { ...kr, start_date: fiscal_start, end_date: fiscal_end },
            plan
        });
    });
}

function render_context_preview(frm, context) {
    const field = frm.fields_dict.context_preview_html;
    if (!field || !field.$wrapper) return;

    const ctx = context || {};
    const kr = ctx.kr || {};
    const plan = ctx.plan || {};

    let timeline_text = __('Select a Key Result to preview its timeline.');
    let timeline_detail = '';
    const start_date = kr.start_date || frm.doc.context_start_date;
    const end_date = kr.end_date || frm.doc.context_end_date;
    if (start_date && end_date) {
        timeline_text = frappe.datetime.str_to_user(start_date)
            + ' → ' + frappe.datetime.str_to_user(end_date);
        timeline_detail = __('{0} Days', [
            frappe.datetime.get_day_diff(end_date, start_date) + 1
        ]);
    }

    const icons = {
        target:   '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
        flag:     '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>',
        plan:     '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
        building: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M3 9h6"/><path d="M3 15h6"/><path d="M15 3v18"/><path d="M15 9h6"/><path d="M15 15h6"/></svg>',
        calendar: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
        clock:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
        notes:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    };

    const cards = [
        { icon: icons.target,   label: __('Key Result'),       value: kr.key_result_title || frm.doc.key_result_title },
        { icon: icons.flag,     label: __('Objective'),        value: kr.objective_title || frm.doc.objective_title },
        { icon: icons.plan,     label: __('Plan'),             value: plan.plan_name || frm.doc.plan_title },
        { icon: icons.building, label: __('Organization'),     value: kr.company || frm.doc.company },
        { icon: icons.calendar, label: __('Financial Year'),   value: kr.financial_year || frm.doc.financial_year },
        { icon: icons.clock,    label: __('Timeline'),         value: timeline_text + (timeline_detail ? ' • ' + timeline_detail : '') },
        { icon: icons.notes,    label: __('Plan Description'), value: plan.description || frm.doc.plan_description, wide: true },
    ];

    render_preview_cards(field, cards, __('Select a Key Result to preview its context.'));
}

function render_preview_cards(field, cards, empty_message) {
    if (window.okr_management && window.okr_management.ui && window.okr_management.ui.render_preview_cards) {
        window.okr_management.ui.render_preview_cards(field, cards, empty_message);
        return;
    }
    if (!field || !field.$wrapper) return;
    const visible_cards = cards || [];
    const escape_html = (val) => frappe.utils.escape_html(String(val ?? "—"));
    const card_html = visible_cards.length
        ? visible_cards.map((card) => {
            if (!card) return "";
            const wide = Boolean(card.wide);
            let val = "—";
            if (card.value !== undefined && card.value !== null && String(card.value).trim() !== "") {
                val = String(card.value);
            }
            const content = card.html
                || '<div style="font-size:13px;font-weight:' + (wide ? '500' : '600') + ';color:#1e293b;line-height:' + (wide ? '1.5' : '1.4') + ';word-break:break-word;white-space:pre-wrap;">'
                    + escape_html(val)
                    + '</div>';
            return '<div style="' + (wide ? 'width:100%;' : 'flex:1 1 45%;min-width:180px;')
                + 'display:flex;align-items:' + (wide ? 'flex-start' : 'center')
                + ';gap:10px;background:#f8f9fc;border:1px solid #e3e8ef;border-radius:10px;padding:10px 14px;">'
                + '<span style="font-size:18px;flex-shrink:0;margin-top:' + (wide ? '2px' : '0') + ';color:#5b6b8a;display:flex;align-items:center;">'
                + (card.icon || "📌") + '</span>'
                + '<div style="min-width:0;">'
                + '<div style="font-size:10px;font-weight:600;color:#8d99ae;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;">'
                + escape_html(__(card.label || "")) + '</div>'
                + content
                + '</div></div>';
        }).join('')
        : '<div style="width:100%;padding:12px 14px;border:1px dashed #d6dbe6;border-radius:10px;color:var(--text-muted);background:#fbfcfe;">'
            + escape_html(empty_message || __("No context available."))
            + '</div>';

    const wrapper_html = '<div style="display:flex;flex-wrap:wrap;gap:12px;">' + card_html + '</div>';
    if (typeof field.set_value === 'function') {
        field.set_value(wrapper_html);
    } else {
        field.$wrapper.html(wrapper_html);
    }
}
