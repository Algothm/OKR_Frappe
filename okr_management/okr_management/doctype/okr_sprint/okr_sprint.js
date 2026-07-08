console.log("OKR Sprint JS Loaded");

frappe.ui.form.on('OKR Sprint', {
    refresh(frm) {
        console.log("refresh called");
        frm.set_df_property('naming_series', 'hidden', 1);

        // Filter parent_plan to Active plans only
        frm.set_query('parent_plan', () => ({ filters: { status: 'Active' } }));

        // Override get_filter_description to completely suppress the "Filters applied for..." banner
        const pf = frm.get_field('parent_plan');
        if (pf) {
            pf.get_filter_description = () => '';
        }

        set_default_sprint_owner(frm);

        apply_sprint_ui_rules(frm);

        fetch_and_cache_parent_plan_title(frm);
    },

    parent_plan(frm) {
        console.log("parent_plan changed");
        console.log("frm.doc.parent_plan: " + frm.doc.parent_plan);
        if (frm.doc.parent_plan) {
            frappe.db.get_value('OKR Plan', frm.doc.parent_plan, 'plan_name').then(r => {
                if (r.message && r.message.plan_name) {
                    frappe.utils.add_link_title("OKR Plan", frm.doc.parent_plan, r.message.plan_name);
                    frm.refresh_field('parent_plan');
                }
            });
        }
        inherit_parent_plan_context(frm);
        calculate_sprint_dates(frm);
    },

    sprint_cycle(frm) {
        console.log("sprint_cycle changed");
        console.log("frm.doc.sprint_cycle: " + frm.doc.sprint_cycle);
        clear_cycle_specific_fields(frm);
        calculate_sprint_dates(frm);
        apply_sprint_ui_rules(frm);
    },

    financial_quarter(frm) {
        console.log("financial_quarter changed");
        console.log("frm.doc.financial_quarter: " + frm.doc.financial_quarter);
        calculate_sprint_dates(frm);
    },

    sprint_month(frm) {
        console.log("sprint_month changed");
        console.log("frm.doc.sprint_month: " + frm.doc.sprint_month);
        calculate_sprint_dates(frm);
    },

    month(frm) {
        console.log("month changed");
        console.log("frm.doc.month: " + frm.doc.month);
        calculate_sprint_dates(frm);
    },

    financial_year(frm) {
        console.log("financial_year changed");
        console.log("frm.doc.financial_year: " + frm.doc.financial_year);
        calculate_sprint_dates(frm);
    },

    status(frm) {
        apply_sprint_ui_rules(frm);
    }
});

function apply_sprint_ui_rules(frm) {
    const status = frm.doc.status || 'Draft';
    const is_draft         = status === 'Draft';
    const is_before_active = ['Draft', 'Planned'].includes(status);
    const is_custom        = frm.doc.sprint_cycle === 'Custom Date Range';
    const setup_locked     = !is_draft;

    // Always required
    frm.toggle_reqd('parent_plan',   true);
    frm.toggle_reqd('sprint_name',   true);
    frm.toggle_reqd('sprint_owner',  true);
    frm.toggle_reqd('sprint_cycle',  true);
    frm.toggle_reqd('financial_quarter', frm.doc.sprint_cycle === 'Financial Quarter');
    frm.toggle_reqd('sprint_month',  frm.doc.sprint_cycle === 'Monthly');

    // Visibility
    frm.toggle_display('financial_quarter', frm.doc.sprint_cycle === 'Financial Quarter');
    frm.toggle_display('sprint_month',      frm.doc.sprint_cycle === 'Monthly');

    // Read-only inherited fields
    ['financial_year', 'company', 'department', 'plan_owner'].forEach((f) => {
        frm.set_df_property(f, 'read_only', 1);
    });
    ['financial_year', 'company', 'start_date', 'end_date'].forEach((f) => {
        frm.set_df_property(f, 'hidden', 0);
    });

    // Setup fields read-only past Draft
    ['parent_plan', 'sprint_cycle', 'financial_quarter', 'sprint_month'].forEach((f) => {
        frm.set_df_property(f, 'read_only', setup_locked);
    });

    frm.set_df_property('sprint_name',  'read_only', !is_before_active);
    frm.set_df_property('sprint_owner', 'read_only', !is_before_active);

    // start_date and end_date: editable ONLY in custom cycle during setup (Draft)
    frm.set_df_property('start_date', 'read_only', setup_locked || !is_custom);
    frm.set_df_property('end_date',   'read_only', setup_locked || !is_custom);

    // Hidden system / raw fields (always hidden from UI)
    ['status', 'progress', 'objective_count', 'sprint_year', 'department', 'plan_owner', 'sprint_duration', 'sprint_owner'].forEach((f) => {
        frm.set_df_property(f, 'hidden', 1);
    });
}

function inherit_parent_plan_context(frm) {
    if (!frm.doc.parent_plan) {
        const p1 = frm.set_value('financial_year', '');
        const p2 = frm.set_value('company', '');
        const p3 = frm.set_value('department', '');
        const p4 = frm.set_value('plan_owner', '');
        const p5 = frm.set_value('start_date', '');
        const p6 = frm.set_value('end_date', '');
        
        frm.refresh_field('financial_year');
        frm.refresh_field('company');
        frm.refresh_field('department');
        frm.refresh_field('plan_owner');
        frm.refresh_field('start_date');
        frm.refresh_field('end_date');
        
        Promise.all([p1, p2, p3, p4, p5, p6]).then(() => {
            frm.refresh_field('financial_year');
            frm.refresh_field('company');
            frm.refresh_field('department');
            frm.refresh_field('plan_owner');
            frm.refresh_field('start_date');
            frm.refresh_field('end_date');
        });
        
        set_default_sprint_owner(frm);
        return;
    }

    frappe.db.get_value(
        'OKR Plan',
        frm.doc.parent_plan,
        ['financial_year', 'company', 'department', 'owner_user']
    ).then((r) => {
        const plan = r.message || {};
        const p1 = frm.set_value('financial_year', plan.financial_year || '');
        const p2 = frm.set_value('company', plan.company || '');
        const p3 = frm.set_value('department', plan.department || '');
        const p4 = frm.set_value('plan_owner', plan.owner_user || '');
        const p5 = frm.set_value('sprint_owner', plan.owner_user || frappe.session.user);
        
        frm.refresh_field('financial_year');
        frm.refresh_field('company');
        frm.refresh_field('department');
        frm.refresh_field('plan_owner');
        frm.refresh_field('sprint_owner');

        Promise.all([p1, p2, p3, p4, p5]).then(() => {
            frm.refresh_field('financial_year');
            frm.refresh_field('company');
            frm.refresh_field('department');
            frm.refresh_field('plan_owner');
            frm.refresh_field('sprint_owner');
            calculate_sprint_dates(frm);
            apply_sprint_ui_rules(frm);
        });
    });
}

function set_default_sprint_owner(frm) {
    if (!frm.doc.sprint_owner) {
        frm.set_value('sprint_owner', frm.doc.plan_owner || frappe.session.user);
    }
}

function clear_cycle_specific_fields(frm) {
    if (frm.doc.sprint_cycle !== 'Financial Quarter') {
        frm.set_value('financial_quarter', '');
    }
    if (frm.doc.sprint_cycle !== 'Monthly') {
        frm.set_value('sprint_month', '');
    }
    frm.set_value('start_date', '');
    frm.set_value('end_date',   '');
}

function calculate_sprint_dates(frm) {
    console.log("calculate_sprint_dates called");
    console.log("frm.doc.parent_plan: " + frm.doc.parent_plan);
    console.log("frm.doc.sprint_cycle: " + frm.doc.sprint_cycle);
    console.log("frm.doc.financial_quarter: " + frm.doc.financial_quarter);
    console.log("frm.doc.month: " + frm.doc.month);
    console.log("frm.doc.sprint_month: " + frm.doc.sprint_month);
    console.log("frm.doc.financial_year: " + frm.doc.financial_year);

    if (!frm.doc.sprint_cycle || !frm.doc.parent_plan) {
        console.log("Missing sprint_cycle or parent_plan, returning early.");
        return;
    }

    if (frm.doc.sprint_cycle === 'Financial Quarter') {
        calculate_financial_quarter_dates(frm);
    } else if (frm.doc.sprint_cycle === 'Monthly') {
        calculate_monthly_dates(frm);
    }
}

function calculate_financial_quarter_dates(frm) {
    if (!frm.doc.financial_quarter || !frm.doc.financial_year) return;

    frappe.db.get_value(
        'Fiscal Year',
        frm.doc.financial_year,
        ['year_start_date']
    ).then((r) => {
        const fy = r.message || {};
        if (!fy.year_start_date) return;

        const quarter_offsets = { Q1: 0, Q2: 3, Q3: 6, Q4: 9 };
        const offset = quarter_offsets[frm.doc.financial_quarter];
        if (offset === undefined) return;

        const start = moment(fy.year_start_date).add(offset, 'months').format('YYYY-MM-DD');
        const end   = moment(start).add(3, 'months').add(-1, 'days').format('YYYY-MM-DD');
        
        const p1 = frm.set_value('start_date', start);
        const p2 = frm.set_value('end_date',   end);
        
        frm.refresh_field('start_date');
        frm.refresh_field('end_date');
        
        Promise.all([p1, p2]).then(() => {
            frm.refresh_field('start_date');
            frm.refresh_field('end_date');
        });
    });
}

function calculate_monthly_dates(frm) {
    if (!frm.doc.sprint_month || !frm.doc.financial_year) return;

    frappe.db.get_value(
        'Fiscal Year',
        frm.doc.financial_year,
        ['year_start_date']
    ).then((r) => {
        const fy = r.message || {};
        if (!fy.year_start_date) return;

        const months = {
            January: 0, February: 1, March: 2, April: 3,
            May: 4, June: 5, July: 6, August: 7,
            September: 8, October: 9, November: 10, December: 11
        };
        const month_index = months[frm.doc.sprint_month];
        if (month_index === undefined) return;

        const fy_start  = moment(fy.year_start_date);
        const fy_start_month = fy_start.month(); // 0-indexed
        const fy_year        = fy_start.year();

        const cal_year = month_index >= fy_start_month ? fy_year : fy_year + 1;
        const p1 = frm.set_value('sprint_year', cal_year);

        const start = moment([cal_year, month_index, 1]).format('YYYY-MM-DD');
        const end   = moment(start).endOf('month').format('YYYY-MM-DD');

        const p2 = frm.set_value('start_date', start);
        const p3 = frm.set_value('end_date',   end);
        
        frm.refresh_field('start_date');
        frm.refresh_field('end_date');
        
        Promise.all([p1, p2, p3]).then(() => {
            frm.refresh_field('start_date');
            frm.refresh_field('end_date');
        });
    });
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
