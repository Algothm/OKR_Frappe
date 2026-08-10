(() => {
    const redirects = {
        "okr-admin-workspace": "/app/admin-workspace",
        "plan": "/app/okr-plan",
        "objective": "/app/okr-objective",
        "key-result": "/app/okr-key-result",
        "action-item": "/app/okr-action-item",
        "check-in": "/app/okr-check-in",
    };

    Object.entries(redirects).forEach(([page_name, destination]) => {
        frappe.pages[page_name].on_page_load = function () {
            window.location.replace(destination);
        };
    });
})();
