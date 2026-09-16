function setup_auto_growing_title(frm, fieldname) {
    const input = frm.fields_dict[fieldname]?.$wrapper?.find('textarea').first();
    if (!input?.length) return;
    input.attr('maxlength', 1000);
    input.off('input.okr-title-resize').on('input.okr-title-resize', () => resize_auto_growing_title(frm, fieldname));
    resize_auto_growing_title(frm, fieldname);
}

function resize_auto_growing_title(frm, fieldname) {
    const input = frm.fields_dict[fieldname]?.$wrapper?.find('textarea').first();
    if (!input?.length) return;
    const textarea = input[0];
    textarea.style.setProperty('height', 'auto', 'important');
    textarea.style.setProperty('min-height', '38px', 'important');
    textarea.style.setProperty('max-height', 'none', 'important');
    textarea.style.setProperty('overflow-y', 'hidden', 'important');
    textarea.style.setProperty('resize', 'none', 'important');
    textarea.style.setProperty('height', Math.max(38, textarea.scrollHeight) + 'px', 'important');
}

frappe.ui.form.on('OKR Action Item', {
    setup(frm) {
        frm.set_query('assigned_to', () => ({ filters: { enabled: 1, user_type: 'System User' } }));
        set_measurement_type_options(frm);
    },
    onload(frm) {
        apply_route_context(frm);
    },
    onload_post_render(frm) {
        if (frm.doc.parent_key_result) fetch_parent_key_result_context(frm);
        else render_context_preview(frm, {});
        setup_auto_growing_title(frm, 'action_item_title');
    },
    refresh(frm) {
        apply_action_item_ui(frm);
        configure_check_in_connection(frm);
        apply_route_context(frm);
        if (frm.doc.parent_key_result) fetch_parent_key_result_context(frm);
        else render_context_preview(frm, {});
        if (frm.doc.action_item_title && !frm.is_new()) frm.page.set_title(frm.doc.action_item_title);
        render_action_completion(frm, flt(frm.doc.progress || 0, 2));
        setup_auto_growing_title(frm, 'action_item_title');
    },
    parent_key_result(frm) {
        fetch_parent_key_result_context(frm);
    },
    due_date(frm) {
        validate_due_date_against_target(frm);
        render_context_preview(frm, frm._kr_context);
    },
    current_value(frm) {
        recalculate_form_action_progress(frm);
    },
    baseline_value(frm) {
        recalculate_form_action_progress(frm);
    },
    target_value(frm) {
        recalculate_form_action_progress(frm);
    },
    metric_direction(frm) {
        recalculate_form_action_progress(frm);
    },
    metric_type(frm) {
        recalculate_form_action_progress(frm);
    },
    validate(frm) {
        if (!frm.doc.assigned_to) {
            frappe.throw(__('Assigned To is required.'));
        }
        if (!validate_due_date_against_target(frm)) {
            frappe.validated = false;
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
        }
    }
});

function configure_check_in_connection(frm) {
    if (frm.is_new() || !frm.dashboard || frm.dashboard._okr_check_in_direct_add) return;

    const open_document_list = frm.dashboard.open_document_list.bind(frm.dashboard);
    frm.dashboard.open_document_list = function ($link, show_open) {
        const doctype = $link?.attr('data-doctype');
        if (doctype === 'OKR Check In' && frm.can_create(doctype)) {
            frappe.new_doc(doctype, { action_item: frm.doc.name });
            return;
        }

        return open_document_list($link, show_open);
    };
    frm.dashboard._okr_check_in_direct_add = true;
}

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
    set_measurement_type_options(frm);
    [
        'parent_plan', 'plan_title', 'plan_description', 'company', 'financial_year',
        'sprint_frequency', 'context_start_date', 'context_end_date',
        'parent_objective', 'objective_title', 'key_result_title',
        'measurement_customization_status'
    ].forEach((fieldname) => frm.set_df_property(fieldname, 'read_only', 1));

	frm.set_df_property('context_preview_html', 'label', __('Context and Preview of Plan, Objective and Key Result'));
	frm.toggle_display('context_preview_html', 1);

    [
        'action_item_setup_heading', 'progress', 'priority', 'status', 'owner_user', 'reviewer', 'group', 'department',
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
    const due_date_field = frm.fields_dict.due_date;

    if (assigned_to_field && assigned_to_field.$wrapper) {
        assigned_to_field.$wrapper.css({
            'width': '48%',
            'display': 'inline-block',
            'margin-right': '3%',
            'vertical-align': 'top'
        });
    }
    if (due_date_field && due_date_field.$wrapper) {
        due_date_field.$wrapper.css({
            'width': '48%',
            'display': 'inline-block',
            'margin-right': '0',
            'vertical-align': 'top'
        });
    }

    if (window.okr_management && window.okr_management.ui && window.okr_management.ui.apply_context_panel_style) {
        window.okr_management.ui.apply_context_panel_style(frm);
    }
}

function clear_context(frm) {
    frm._kr_context = null;
    frm._plan_context = null;
    [
        'parent_plan', 'plan_title', 'plan_description', 'company', 'financial_year', 'sprint_frequency',
        'context_start_date', 'context_end_date', 'parent_objective', 'objective_title', 'key_result_title'
    ].forEach((fieldname) => frm.set_value(fieldname, ''));
    render_context_preview(frm, {});
}

function set_due_date_target_guidance(frm, target_date, show_message = false) {
    const message = show_message && target_date
        ? __('Key Result Target Date: {0}. Due Date must be on or before this date and inside the same target period.', [frappe.datetime.str_to_user(target_date)])
        : '';
    frm.set_df_property('due_date', 'description', message);
}

function validate_due_date_against_target(frm) {
    if (!frm.doc.due_date || !frm.doc.context_end_date) {
        set_due_date_target_guidance(frm, frm.doc.context_end_date, false);
        return true;
    }
    const before_start = frm.doc.context_start_date
        && moment(frm.doc.due_date).isBefore(frm.doc.context_start_date, 'day');
    const after_end = moment(frm.doc.due_date).isAfter(frm.doc.context_end_date, 'day');
    const is_invalid = Boolean(before_start || after_end);
    set_due_date_target_guidance(frm, frm.doc.context_end_date, is_invalid);
    return !is_invalid;
}

function format_user_display(user_id) {
    if (!user_id) return '';
    if (window.frappe && frappe.user_info && frappe.user_info(user_id)) {
        const info = frappe.user_info(user_id);
        const name = info.fullname || info.full_name;
        if (name && name.trim() && name.trim() !== user_id.trim()) {
            return name.trim();
        }
    }
    return user_id;
}

function fetch_parent_key_result_context(frm) {
    if (!frm.doc.parent_key_result) {
        clear_context(frm);
        return;
    }
    const selected_key_result = frm.doc.parent_key_result;
    frappe.db.get_value('OKR Key Result', selected_key_result, [
        'key_result_title', 'objective', 'parent_plan', 'company', 'group', 'department',
        'financial_year', 'start_date', 'end_date', 'reviewer', 'objective_title',
        'assignee', 'owner_user', 'objective_owner', 'description',
        'lock_measurement_fields_for_action_item_assignees', 'metric_type', 'metric_direction',
        'baseline_value', 'target_value', 'current_value'
    ]).then((response) => {
        if (frm.doc.parent_key_result !== selected_key_result) return;
        const kr = response.message || {};

        const finalize_kr_context = (kr_data) => {
            frm._kr_context = { kr: kr_data, plan: frm._plan_context || {} };
            set_due_date_target_guidance(frm, kr_data.end_date, false);
            frappe.utils.add_link_title('OKR Key Result', selected_key_result, kr_data.key_result_title || selected_key_result);
            const values = {
                parent_objective: kr_data.objective || '',
                objective_title: kr_data.objective_title || '',
                parent_plan: kr_data.parent_plan || '',
                company: kr_data.company || '',
                group: kr_data.group || '',
                department: kr_data.department || '',
                context_start_date: kr_data.start_date || '',
                context_end_date: kr_data.end_date || '',
                key_result_title: kr_data.key_result_title || ''
            };
            if (frm.is_new() && !frm.doc.due_date && kr_data.end_date) {
                values.due_date = kr_data.end_date;
            }
            if (!frm.doc.reviewer) values.reviewer = kr_data.reviewer || '';
            frm.doc.financial_year = kr_data.financial_year || '';
            frm.refresh_field('financial_year');
            frm.set_value(values);
            load_plan_context(frm, kr_data.parent_plan, kr_data);
            const is_locked = Boolean(kr_data.lock_measurement_fields_for_action_item_assignees === 0 || kr_data.lock_measurement_fields_for_action_item_assignees === '0');
            frm.set_value('measurement_customization_status', is_locked ? 'Locked' : 'Allowed');
            update_measurement_customization_ui(frm, is_locked, kr_data);
            render_action_completion(frm, flt(frm.doc.progress || 0, 2));
        };

        if ((!kr.objective_owner || !kr.group) && kr.objective) {
            frappe.db.get_value('OKR Objective', kr.objective, ['owner_user', 'owner', 'group']).then((obj_res) => {
                const obj_data = obj_res.message || {};
                if (!kr.objective_owner) {
                    kr.objective_owner = obj_data.owner_user || obj_data.owner || '';
                }
                if (!kr.group) {
                    kr.group = obj_data.group || '';
                }
                finalize_kr_context(kr);
            });
        } else {
            finalize_kr_context(kr);
        }
    });
}

function load_plan_context(frm, plan_name, kr) {
    const active_kr = kr || (frm._kr_context && frm._kr_context.kr) || {};
    if (!plan_name) {
        frm.set_value({
            plan_title: '',
            plan_description: '',
            sprint_frequency: '',
        });
        frm._plan_context = {};
        frm._kr_context = { kr: active_kr, plan: {} };
        render_context_preview(frm, frm._kr_context);
        return;
    }
    frappe.call({
        method: 'okr_management.okr_management.doctype.okr_plan.okr_plan.get_plan_context',
        args: { plan_name }
    }).then((response) => {
        const plan = response.message || {};
        if (plan.plan_name) frappe.utils.add_link_title('OKR Plan', plan_name, plan.plan_name);
        frm.doc.financial_year = plan.financial_year || frm.doc.financial_year || '';
        frm.refresh_field('financial_year');
        frm.set_value({
            plan_title: plan.plan_name || '',
            plan_description: plan.description || '',
            sprint_frequency: plan.sprint_frequency || '',
        });
        frm._plan_context = plan;
        frm._kr_context = { kr: active_kr, plan };
        render_context_preview(frm, frm._kr_context);
    });
}

function render_context_preview(frm, context) {
    const field = frm.fields_dict.context_preview_html;
    if (!field || !field.$wrapper) return;

    const ctx = context || frm._kr_context || {};
    const kr = ctx.kr || (frm._kr_context && frm._kr_context.kr) || {};
    const plan = ctx.plan || (frm._kr_context && frm._kr_context.plan) || frm._plan_context || {};

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
        group:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
        building: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M3 9h6"/><path d="M3 15h6"/><path d="M15 3v18"/><path d="M15 9h6"/><path d="M15 15h6"/></svg>',
        calendar: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
        clock:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
        notes:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
        user:     '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    };

    const kr_owner_raw = kr.assignee || kr.owner_user || (frm._kr_context && frm._kr_context.kr && (frm._kr_context.kr.assignee || frm._kr_context.kr.owner_user)) || '';
    const obj_owner_raw = kr.objective_owner || (frm._kr_context && frm._kr_context.kr && frm._kr_context.kr.objective_owner) || '';
    const kr_group_raw = kr.group || (frm._kr_context && frm._kr_context.kr && frm._kr_context.kr.group) || frm.doc.group || '';

    const cards = [
        { icon: icons.target,   label: __('Key Result'),       value: kr.key_result_title || frm.doc.key_result_title },
        { icon: icons.flag,     label: __('Objective'),        value: kr.objective_title || frm.doc.objective_title },
        { icon: icons.plan,     label: __('Plan'),             value: plan.plan_name || frm.doc.plan_title },
        { icon: icons.building, label: __('Organization'),     value: kr.company || frm.doc.company },
        { icon: icons.group,    label: __('Group'),            value: kr_group_raw },
        { icon: icons.calendar, label: __('Financial Year'),   value: kr.financial_year || frm.doc.financial_year },
        { icon: icons.clock,    label: __('Key Result Timeline'), value: timeline_text + (timeline_detail ? ' • ' + timeline_detail : '') },
        { icon: icons.user,     label: __('Key Result Owner'),  value: format_user_display(kr_owner_raw) },
        { icon: icons.user,     label: __('Objective Owner'),   value: format_user_display(obj_owner_raw) },
        { icon: icons.notes,    label: __('Key Result Description'), value: kr.description || plan.description || frm.doc.plan_description, wide: true },
    ];

    render_preview_cards(field, cards, __('Select a Key Result to preview its context.'));
}

function render_preview_cards(field, cards, empty_message, title) {
    if (!field || !field.$wrapper) return;
    const visible_cards = cards || [];
    const escape_html = (val) => frappe.utils.escape_html(String(val ?? "—"));
    const header_title = title || __("Context and Preview of Plan, Objective and Key Result");

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

    const title_html = '<div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:10px;">'
        + escape_html(header_title)
        + '</div>';

    const cards_box_html = '<div style="border:1.5px solid #cbd5e0;border-radius:10px;background:#fafbff;padding:16px 18px;box-shadow:0 1px 6px rgba(0,0,0,0.06);display:flex;flex-wrap:wrap;gap:12px;">'
        + card_html
        + '</div>';

    field.$wrapper.prev('.okr-context-heading').remove();
    $(title_html).addClass('okr-context-heading').insertBefore(field.$wrapper);
    const full_html = cards_box_html;

    if (field.$wrapper && field.$wrapper[0]) {
        field.$wrapper[0].innerHTML = full_html;
    } else if (typeof field.set_value === 'function') {
        field.set_value(full_html);
    }

    if (field.$wrapper) {
        field.$wrapper.css({
            'border': 'none',
            'border-radius': '0',
            'background': 'transparent',
            'padding': '0',
            'box-shadow': 'none',
            'display': 'block'
        });
    }
}

function set_measurement_type_options(frm) {
    frm.set_df_property('metric_type', 'options', [
        { label: __('Percentage'), value: 'Percentage' },
        { label: __('Number'), value: 'Number' },
        { label: __('Amount'), value: 'Currency' }
    ]);
}

function update_measurement_customization_ui(frm, is_locked, kr_data) {
    frm.set_df_property('measurement_customization_status', 'read_only', 1);
    frm.set_df_property('customize_measurement', 'hidden', 1);

    const user = frappe.session.user;
    const is_admin = (user === 'Administrator' || (frappe.user_roles && (frappe.user_roles.includes('System Manager') || frappe.user_roles.includes('OKR Admin'))));
    const is_assignee = (frm.doc.assigned_to === user || is_admin);
    const is_editable_status = ['Open', 'In Progress', 'On Hold', 'Blocked'].includes(frm.doc.status || 'Open');
    const can_customize = !is_locked && is_assignee && is_editable_status;

    frm.set_df_property('measurement_section', 'hidden', 0);
    if (!is_locked && !frm.doc.customize_measurement) {
        frm.set_value('metric_type', kr_data.metric_type || 'Percentage');
        frm.set_value('metric_direction', kr_data.metric_direction || 'Increase');
        frm.set_value('baseline_value', flt(kr_data.baseline_value, 2));
        frm.set_value('target_value', flt(kr_data.target_value, 2));
        frm.set_value('current_value', flt(frm.is_new() ? kr_data.baseline_value : (frm.doc.current_value ?? kr_data.baseline_value), 2));
        frm.set_value('customize_measurement', 1);
    }
    ['metric_type', 'metric_direction', 'baseline_value', 'target_value', 'current_value'].forEach((f) => {
        frm.set_df_property(f, 'read_only', can_customize ? 0 : 1);
    });
}

function recalculate_form_action_progress(frm) {
    if (!frm.doc.customize_measurement) return;
    const actual = flt(frm.doc.current_value);
    const baseline = flt(frm.doc.baseline_value);
    const target = flt(frm.doc.target_value);
    let progress = 0;
    if (frm.doc.metric_type === 'Percentage') {
        progress = Math.min(100, Math.max(0, actual));
    } else if (frm.doc.metric_type === 'Boolean') {
        progress = actual ? 100 : 0;
    } else if (target !== baseline) {
        if (frm.doc.metric_direction === 'Decrease') {
            progress = ((baseline - actual) / (baseline - target)) * 100;
        } else {
            progress = ((actual - baseline) / (target - baseline)) * 100;
        }
        progress = Math.min(100, Math.max(0, Math.round(progress * 100) / 100));
    }
    frm.set_value('progress', progress);
    render_action_completion(frm, progress);
}

function render_action_completion(frm, progress_value) {
    const field = frm.fields_dict.current_value;
    if (!field || !field.$wrapper) return;

    const progress = Math.min(100, Math.max(0, flt(progress_value || 0, 2)));
    const progress_text = Number.isInteger(progress) ? String(progress) : String(flt(progress, 2));
    field.$wrapper.find('.okr-live-completion').remove();
    const preview = $(`
        <div class="okr-live-completion" style="margin-top:10px;padding:10px 12px;border:1px solid var(--border-color);border-radius:8px;background:var(--subtle-fg);">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:7px;font-size:12px;">
                <span style="color:var(--text-muted);font-weight:600;">${__('Calculated completion')}</span>
                <strong style="color:var(--text-color);">${progress_text}%</strong>
            </div>
            <div style="height:6px;border-radius:999px;background:var(--gray-200);overflow:hidden;">
                <div style="height:100%;width:${progress}%;border-radius:inherit;background:var(--primary);transition:width .2s ease;"></div>
            </div>
        </div>
    `);
    const description = field.$wrapper.find('.help-box').last();
    if (description.length) preview.insertAfter(description);
    else field.$wrapper.append(preview);
}
