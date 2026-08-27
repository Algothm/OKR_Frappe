(() => {
    const has_role = (r) => (
        (frappe.user && frappe.user.has_role && frappe.user.has_role(r))
        || ((frappe.boot && frappe.boot.user && frappe.boot.user.roles) ? frappe.boot.user.roles.includes(r) : false)
        || ((frappe.user_roles) ? frappe.user_roles.includes(r) : false)
    );
    const is_admin = () => (
        frappe.session.user === "Administrator" || has_role("OKR Admin") || has_role("System Manager")
    );
    const is_okr_user = () => (
        is_admin()
        || has_role("OKR User")
        || has_role("Employee")
        || has_role("Team Lead")
        || has_role("Department Head")
        || (frappe.session.user && frappe.session.user !== "Guest")
    );

    function get_route_for_item(itemName) {
        // Sidebar visibility is decided by the server. Keep route targets
    // unconditional so early Desk initialization can never rewrite a valid
    // OKR link to /app/home before roles are available in the browser.
    const routes = {
        "OKR Admin Workspace": "/app/admin-workspace",
        "Admin Workspace": "/app/admin-workspace",
        "Plan": "/app/okr-plan",
        "OKR Plan Planning": "/app/okr-plan",
        "OKR Workspace": "/app/okr-workspace",
        "Objective": "/app/okr-objective",
        "OKR Objective Execution": "/app/okr-objective",
        "Key Result": "/app/okr-key-result",
        "OKR Key Result Execution": "/app/okr-key-result",
        "Action Item": "/app/okr-action-item",
        "OKR Action Item Execution": "/app/okr-action-item",
        "Check-In": "/app/okr-check-in",
    };
        return routes[itemName];
    }

    function bind_links() {
        document.querySelectorAll(".sidebar-item-container[item-name]").forEach((item) => {
            const url = get_route_for_item(item.getAttribute("item-name"));
            if (!url) return;
            const anchor = item.querySelector(":scope > .desk-sidebar-item > a.item-anchor");
            if (anchor) anchor.href = url;
        });
    }

    document.addEventListener("click", (event) => {
        const item = event.target.closest && event.target.closest(".sidebar-item-container[item-name]");
        if (!item || event.target.closest("button.drop-icon")) return;
        const anchor = event.target.closest("a.item-anchor");
        const url = get_route_for_item(item.getAttribute("item-name"));
        if (!anchor || !url) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        frappe.set_route(url.replace(/^\/app\//, ""));
    }, true);

    bind_links();
    document.addEventListener("DOMContentLoaded", bind_links);
    new MutationObserver(bind_links).observe(document.documentElement, {childList: true, subtree: true});
    window.setInterval(bind_links, 500);
})();
