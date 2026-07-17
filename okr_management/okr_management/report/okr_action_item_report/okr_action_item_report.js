frappe.query_reports['OKR Action Item Report'] = {
    filters: [
        {fieldname: 'plan', label: __('Plan'), fieldtype: 'Link', options: 'OKR Plan'},
        {fieldname: 'objective', label: __('Objective'), fieldtype: 'Link', options: 'OKR Objective'},
        {fieldname: 'key_result', label: __('Key Result'), fieldtype: 'Link', options: 'OKR Key Result'},
        {fieldname: 'owner', label: __('Owner'), fieldtype: 'Link', options: 'User'},
        {fieldname: 'status', label: __('Status'), fieldtype: 'Select', options: '\nDraft\nNot Started\nIn Progress\nBlocked\nCompleted\nCancelled'},
        {fieldname: 'priority', label: __('Priority'), fieldtype: 'Select', options: '\nLow\nMedium\nHigh\nCritical'},
    ]
};
