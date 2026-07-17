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
    },

    action_item(frm) {
        load_action_item_context(frm);
    },

    progress(frm) {
        frm.set_value('current_value', frm.doc.progress || 0);
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
    frm.set_df_property('action_item', 'read_only', 0);
    frm.set_df_property('action_item', 'reqd', 1);
    frm.set_df_property('progress', 'reqd', 1);
    frm.set_df_property('action_status', 'reqd', 1);
    frm.set_df_property('achievements', 'reqd', 1);

    const field = frm.fields_dict.action_item;
    if (field) {
        field.df.only_select = 1;
        field.df.show_title_field_in_link = 1;
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
            const updates = {};
            Object.keys(context).forEach(fieldname => {
                if (frm.fields_dict[fieldname]) {
                    updates[fieldname] = context[fieldname] || '';
                }
            });
            frm.set_value(updates).then(() => render_context_preview(frm));
        }
    });
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

    const esc = v => frappe.utils.escape_html(String(v || '—'));
    const doc = frm.doc;

    // Pill: icon + label + value in a styled box, two per row
    const pill = (icon, label, value) => `
        <div style="flex:1 1 45%;min-width:180px;display:flex;align-items:center;gap:10px;background:#f8f9fc;border:1px solid #e3e8ef;border-radius:10px;padding:10px 14px;">
            <span style="font-size:18px;flex-shrink:0;">${icon}</span>
            <div style="min-width:0;">
                <div style="font-size:10px;font-weight:600;color:#8d99ae;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;">${__(label)}</div>
                <div style="font-size:13px;font-weight:600;color:#1e293b;line-height:1.4;word-break:break-word;">${esc(value)}</div>
            </div>
        </div>`;

    // Full-width row for longer descriptions
    const wide = (icon, label, value) => `
        <div style="width:100%;display:flex;align-items:flex-start;gap:10px;background:#f8f9fc;border:1px solid #e3e8ef;border-radius:10px;padding:10px 14px;">
            <span style="font-size:18px;flex-shrink:0;margin-top:2px;">${icon}</span>
            <div style="min-width:0;">
                <div style="font-size:10px;font-weight:600;color:#8d99ae;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:2px;">${__(label)}</div>
                <div style="font-size:13px;font-weight:500;color:#1e293b;line-height:1.5;word-break:break-word;">${esc(value)}</div>
            </div>
        </div>`;

    const html = `
        <div style="display:flex;flex-wrap:wrap;gap:12px;">
            ${pill('📊', 'Progress', doc.progress_overview_context)}
            ${pill('👤', 'Assigned To', doc.assigned_to_context)}

            ${pill('🎯', 'Key Result', doc.key_result_name_context)}
            ${pill('🚩', 'Objective', doc.objective_name_context)}

            ${wide('📝', 'Key Result Description', doc.key_result_description_context)}
            ${wide('📝', 'Objective Description', doc.objective_description_context)}

            ${pill('📋', 'Plan', doc.plan_name_context)}
            ${pill('🏢', 'Organization', doc.organization_context)}

            ${wide('📄', 'Plan Description', doc.plan_description_context)}

            ${pill('📅', 'Financial Year', doc.financial_year_context)}
            ${pill('🕐', 'Timeline', doc.timeline_preview_context)}
        </div>`;

    field.$wrapper.html(html);
}

