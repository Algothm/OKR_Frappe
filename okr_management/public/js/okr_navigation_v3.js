(() => {
    const admin = frappe.session.user === "Administrator" || frappe.user.has_role("OKR Admin");
    const okr_user = frappe.user.has_role("OKR User");
    const admin_only = admin && !okr_user;
    const fallback = admin ? "/app/admin-workspace" : okr_user ? "/app/okr-workspace" : "/app/home";
    const routes = {
        "OKR Admin Workspace": admin ? "/app/admin-workspace" : fallback,
        "Plan": admin ? "/app/okr-plan" : fallback,
        "OKR Workspace": okr_user ? "/app/okr-workspace" : fallback,
        "Objective": okr_user ? "/app/okr-objective" : fallback,
        "Key Result": okr_user ? "/app/okr-key-result" : fallback,
        "Action Item": okr_user ? "/app/okr-action-item" : fallback,
        "Check-In": okr_user ? "/app/okr-check-in" : fallback,
    };

    function leave_obsolete_route() {
        if (window.location.pathname !== "/app/okr-management") return false;
        window.location.replace(fallback);
        return true;
    }

    function bind_links() {
        document.querySelectorAll(".sidebar-item-container[item-name]").forEach((item) => {
            const url = routes[item.getAttribute("item-name")];
            if (!url) return;
            const anchor = item.querySelector(":scope > .desk-sidebar-item > a.item-anchor");
            if (anchor) anchor.href = url;
        });
    }

    document.addEventListener("click", (event) => {
        const item = event.target.closest && event.target.closest(".sidebar-item-container[item-name]");
        if (!item || event.target.closest("button.drop-icon")) return;
        const anchor = event.target.closest("a.item-anchor");
        const url = routes[item.getAttribute("item-name")];
        if (!anchor || !url) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        window.location.href = url;
    }, true);

    if (leave_obsolete_route()) return;
    bind_links();
    document.addEventListener("DOMContentLoaded", bind_links);
    new MutationObserver(bind_links).observe(document.documentElement, {childList: true, subtree: true});
    window.setInterval(() => {
        bind_links();
        leave_obsolete_route();
    }, 500);
})();
