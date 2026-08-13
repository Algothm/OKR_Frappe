frappe.ui.form.on('OKR Check In', {
    setup(frm) {
        const action_item_meta = frappe.get_meta('OKR Action Item');
        if (action_item_meta) action_item_meta.show_title_field_in_link = 1;
        frm.set_query('action_item', () => ({
            query: 'okr_management.okr_management.doctype.okr_check_in.okr_check_in.get_assigned_action_items'
        }));
    },

    onload(frm) {
        apply_route_context(frm);
    },

    refresh(frm) {
        configure_form(frm);
        render_context_preview(frm);
        if (frm.is_new() && frm.doc.action_item) {
            load_action_item_context(frm);
        }
        if (!frm.is_new() && frm.doc.status === 'Submitted') {
            frm.add_custom_button(__('New Check-In'), () => {
                frappe.route_options = { action_item: frm.doc.action_item };
                frappe.new_doc('OKR Check In');
            });
        }
    },

    action_item(frm) {
        load_action_item_context(frm);
    },


    validate(frm) {
        if (!frm.doc.action_item) {
            frappe.throw(__('Action Item is required.'));
        }
        if (!frm.doc.achievements) {
            frappe.throw(__('Progress Update is required.'));
        }
    }
});

function configure_form(frm) {
    const is_submitted = !frm.is_new() && frm.doc.status === 'Submitted';
    ['action_item', 'current_value', 'action_status', 'achievements', 'attachment'].forEach(
        (fieldname) => frm.set_df_property(fieldname, 'read_only', is_submitted)
    );
    if (is_submitted) frm.disable_save();

    frm.set_df_property('action_item', 'read_only', is_submitted);
    frm.set_df_property('action_item', 'reqd', 1);
    frm.set_df_property('current_value', 'reqd', 1);
    frm.set_df_property('progress', 'hidden', 1);
    frm.set_df_property('action_status', 'reqd', 1);
    frm.set_df_property('achievements', 'reqd', 1);
    frm.set_df_property('checkin_update_heading', 'hidden', 1);
    frm.set_df_property('context_preview_html', 'label', '');
    frm.toggle_display('context_preview_html', 1);

    const field = frm.fields_dict.action_item;
    if (field) {
        field.df.only_select = 1;
        field.df.show_title_field_in_link = 1;
    }

    if (window.okr_management && window.okr_management.ui && window.okr_management.ui.apply_context_panel_style) {
        window.okr_management.ui.apply_context_panel_style(frm);
    }
}

function apply_route_context(frm) {
    if (!frm.is_new()) return;

    const route_options = frappe.route_options || {};
    const action_item = route_options.action_item || frappe.okr_checkin_action_item;
    frappe.okr_checkin_action_item = null;
    frappe.route_options = null;

    if (action_item) {
        frm.set_value('action_item', action_item);
    }
}

function load_action_item_context(frm) {
    if (!frm.doc.action_item) {
        clear_context(frm);
        return;
    }

    frappe.call({
        method: 'okr_management.okr_management.doctype.okr_check_in.okr_check_in.get_action_item_context',
        args: { action_item: frm.doc.action_item },
        freeze: false,
        callback(r) {
            const context = r.message || {};
            frm.okr_metric = context.metric || {};
            configure_metric_value(frm);
            const updates = {};
            Object.keys(context).forEach(fieldname => {
                if (frm.fields_dict[fieldname]) {
                    updates[fieldname] = context[fieldname] ?? '';
                }
            });
            const financial_year = updates.financial_year || '';
            delete updates.financial_year;
            frm.doc.financial_year = financial_year;
            frm.refresh_field('financial_year');
            frm.set_value(updates).then(() => {
                render_context_preview(frm);
            });
        }
    });
}

function configure_metric_value(frm) {
    const metric = frm.okr_metric || {};
    const baseline = flt(metric.baseline_value || 0, 2);
    const target = flt(metric.target_value || 0, 2);
    const minimum = Math.min(baseline, target);
    const maximum = Math.max(baseline, target);
    frm.set_df_property('current_value', 'label', __('Progress'));

    frm.set_df_property('current_value', 'description', __('Allowed range: {0} to {1}. Completion is calculated automatically.', [minimum, maximum]));
    const field = frm.fields_dict.current_value;
    if (field && field.$input) {
        field.$input.attr({ min: minimum, max: maximum, step: 0.01 });
    }
}

function clear_context(frm) {
    [
        'action_item_title_context', 'progress_overview_context',
        'key_result_name_context', 'key_result_description_context',
        'objective_name_context', 'objective_description_context',
        'plan_name_context', 'plan_description_context',
        'organization_context', 'financial_year_context',
        'timeline_preview_context', 'assigned_to_context'
    ].forEach(fieldname => frm.set_value(fieldname, ''));
    render_context_preview(frm);
}


function render_context_preview(frm) {
    const field = frm.fields_dict.context_preview_html;
    if (!field) return;

    const icons = {
        chart:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
        user:     '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
        target:   '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
        flag:     '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>',
        notes:    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
        plan:     '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
        building: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M3 9h6"/><path d="M3 15h6"/><path d="M15 3v18"/><path d="M15 9h6"/><path d="M15 15h6"/></svg>',
        calendar: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    };

    render_preview_cards(field, [
        { icon: icons.chart,    label: __('Progress'),                 value: frm.doc.progress_overview_context },
        { icon: icons.user,     label: __('Assigned To'),              value: frm.doc.assigned_to_context },
        { icon: icons.target,   label: __('Key Result'),               value: frm.doc.key_result_name_context },
        { icon: icons.flag,     label: __('Objective'),                value: frm.doc.objective_name_context },
        { icon: icons.notes,    label: __('Key Result Description'),   value: frm.doc.key_result_description_context, wide: true },
        { icon: icons.notes,    label: __('Objective Description'),    value: frm.doc.objective_description_context, wide: true },
        { icon: icons.plan,     label: __('Plan'),                     value: frm.doc.plan_name_context },
        { icon: icons.building, label: __('Organization'),             value: frm.doc.organization_context },
        { icon: icons.notes,    label: __('Plan Description'),         value: frm.doc.plan_description_context, wide: true },
        { icon: icons.calendar, label: __('Financial Year'),           value: frm.doc.financial_year_context }
    ], __('No context available.'));
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

    const full_html =
        '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        + 'letter-spacing:0.08em;margin-bottom:12px;padding-bottom:8px;'
        + 'border-bottom:1px solid #e2e8f0;">'
        + __('Context and Preview')
        + '</div>'
        + '<div style="display:flex;flex-wrap:wrap;gap:12px;">' + card_html + '</div>';

    field.$wrapper[0].innerHTML = full_html;
    if (field.df) field.df.options = full_html;

    field.$wrapper.css({
        'border': '1.5px solid #cbd5e0',
        'border-radius': '10px',
        'background': '#fafbff',
        'padding': '16px 18px',
        'box-shadow': '0 1px 6px rgba(0,0,0,0.06)',
        'display': 'block'
    });
}


