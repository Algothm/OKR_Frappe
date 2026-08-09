(() => {
    const admin = frappe.session.user === "Administrator";
    const routes = {
        "OKR Admin Workspace": admin ? "/app/admin-workspace" : "/app/okr-workspace",
        "Plan": admin ? "/app/okr-plan" : "/app/okr-workspace",
        "OKR Workspace": admin ? "/app/admin-workspace" : "/app/okr-workspace",
        "Objective": "/app/okr-objective",
        "Key Result": "/app/okr-key-result",
        "Action Item": "/app/okr-action-item",
        "Check-In": "/app/okr-check-in",
    };

    function leave_obsolete_route() {
        if (window.location.pathname !== "/app/okr-management") return false;
        window.location.replace(admin ? "/app/admin-workspace" : "/app/okr-workspace");
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
