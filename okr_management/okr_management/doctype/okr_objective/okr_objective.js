frappe.ui.form.on('OKR Objective', {
    refresh(frm) {
        frm.set_df_property('naming_series', 'hidden', 1);
        set_sprint_query(frm);
        set_static_properties(frm);
        apply_lifecycle_locks(frm);
        apply_completion_ui(frm);
        fetch_and_cache_parent_plan_title(frm);

        if (frm.is_new() && !frm.doc.status) {
            frm.set_value('status', 'Draft');
        }
        if (!frm.doc.owner_user) {
            frm.set_value('owner_user', frappe.session.user);
        }
        if (!frm.doc.priority) {
            frm.set_value('priority', 'High');
        }
    },
    sprint(frm) {
        inherit_from_sprint(frm);
    },
    status(frm) {
        apply_lifecycle_locks(frm);
        apply_completion_ui(frm);
    },
    partial_completion_accepted(frm) {
        apply_completion_ui(frm);
    },
    start_date(frm) {
        validate_dates_within_sprint(frm);
    },
    end_date(frm) {
        validate_dates_within_sprint(frm);
    }
});

function set_sprint_query(frm) {
    frm.set_query('sprint', () => ({
        filters: {
            status: ['not in', ['Closed', 'Archived']]
        }
    }));
}

function set_static_properties(frm) {
    [
        'naming_series',
        'parent_plan',
        'financial_year',
        'company',
        'department',
        'plan_owner',
        'sprint_owner',
        'start_date',
        'end_date',
        'progress',
        'key_result_count',
        'confidence'
    ].forEach(fieldname => frm.set_df_property(fieldname, 'read_only', 1));
}

function fetch_and_cache_parent_plan_title(frm) {
    if (frm.doc.parent_plan) {
        frappe.db.get_value('OKR Plan', frm.doc.parent_plan, 'plan_name').then(r => {
            if (r.message && r.message.plan_name) {
                frappe.utils.add_link_title("OKR Plan", frm.doc.parent_plan, r.message.plan_name);
                frm.refresh_field('parent_plan');
            }
        });
    }
}

function inherit_from_sprint(frm) {
    if (!frm.doc.sprint) {
        update_sprint_fields(frm, {});
        return;
    }

    frappe.db.get_value('OKR Sprint', frm.doc.sprint, [
        'parent_plan',
        'financial_year',
        'company',
        'department',
        'plan_owner',
        'sprint_owner',
        'start_date',
        'end_date'
    ]).then(r => {
        const sprint = r.message || {};
        if (sprint.parent_plan) {
            frappe.db.get_value('OKR Plan', sprint.parent_plan, 'plan_name').then(p => {
                const plan_name = p.message ? p.message.plan_name : '';
                if (plan_name) {
                    frappe.utils.add_link_title("OKR Plan", sprint.parent_plan, plan_name);
                }
                update_sprint_fields(frm, sprint);
            });
        } else {
            update_sprint_fields(frm, sprint);
        }
    });
}

function update_sprint_fields(frm, sprint) {
    const p1 = frm.set_value('parent_plan', sprint.parent_plan || '');
    const p2 = frm.set_value('financial_year', sprint.financial_year || '');
    const p3 = frm.set_value('company', sprint.company || '');
    const p4 = frm.set_value('department', sprint.department || '');
    const p5 = frm.set_value('plan_owner', sprint.plan_owner || '');
    const p6 = frm.set_value('sprint_owner', sprint.sprint_owner || '');
    const p7 = frm.set_value('start_date', sprint.start_date || '');
    const p8 = frm.set_value('end_date', sprint.end_date || '');

    frm.refresh_field('parent_plan');
    frm.refresh_field('financial_year');
    frm.refresh_field('company');
    frm.refresh_field('department');
    frm.refresh_field('plan_owner');
    frm.refresh_field('sprint_owner');
    frm.refresh_field('start_date');
    frm.refresh_field('end_date');

    Promise.all([p1, p2, p3, p4, p5, p6, p7, p8]).then(() => {
        frm.refresh_field('parent_plan');
        frm.refresh_field('financial_year');
        frm.refresh_field('company');
        frm.refresh_field('department');
        frm.refresh_field('plan_owner');
        frm.refresh_field('sprint_owner');
        frm.refresh_field('start_date');
        frm.refresh_field('end_date');
    });
}

function validate_dates_within_sprint(frm, sprint_values) {
    if (!frm.doc.sprint || !frm.doc.start_date || !frm.doc.end_date) {
        return;
    }
    const validate = sprint => {
        if (!sprint.start_date || !sprint.end_date) return;
        if (frm.doc.start_date < sprint.start_date) {
            frappe.msgprint(__('Objective Start Date cannot be before Sprint Start Date ({0}).', [frappe.datetime.str_to_user(sprint.start_date)]));
        }
        if (frm.doc.end_date > sprint.end_date) {
            frappe.msgprint(__('Objective End Date cannot be after Sprint End Date ({0}).', [frappe.datetime.str_to_user(sprint.end_date)]));
        }
        if (frm.doc.start_date > frm.doc.end_date) {
            frappe.msgprint(__('Objective End Date cannot be before Start Date.'));
        }
    };
    if (sprint_values) {
        validate(sprint_values);
    } else {
        frappe.db.get_value('OKR Sprint', frm.doc.sprint, ['start_date', 'end_date']).then(r => validate(r.message || {}));
    }
}

function apply_lifecycle_locks(frm) {
    const status = frm.doc.status || 'Draft';
    const setup_locked = ['Active', 'On Hold', 'Completed', 'Closed'].includes(status);
    const active_locked = ['Active', 'On Hold', 'Completed', 'Closed'].includes(status);
    const closed_locked = ['Closed'].includes(status);

    ['parent_plan', 'sprint', 'financial_year', 'company', 'department', 'plan_owner', 'sprint_owner', 'level', 'start_date', 'end_date']
    .forEach(fieldname => frm.set_df_property(fieldname, 'read_only', setup_locked || frm.get_field(fieldname).df.read_only));

    ['objective_title', 'owner_user'].forEach(fieldname => frm.set_df_property(fieldname, 'read_only', active_locked));
    ['priority', 'reviewer', 'description', 'partial_completion_accepted', 'completion_notes']
    .forEach(fieldname => frm.set_df_property(fieldname, 'read_only', closed_locked));

    set_static_properties(frm);
}

function apply_completion_ui(frm) {
    const is_completion_state = ['Completed', 'Closed'].includes(frm.doc.status);
    frm.toggle_display('partial_completion_accepted', is_completion_state);
    frm.toggle_display('completion_notes', is_completion_state && cint(frm.doc.partial_completion_accepted));
}
