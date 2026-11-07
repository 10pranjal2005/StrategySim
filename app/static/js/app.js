
/* =========================================================
   StrategySim - Shared Frontend JavaScript
   ========================================================= */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    initializeSidebar();
});


/**
 * Initialize the responsive sidebar.
 */
function initializeSidebar() {
    const sidebar = document.getElementById("appSidebar");
    const toggleButton = document.getElementById("sidebarToggle");
    const closeButton = document.getElementById("sidebarClose");
    const backdrop = document.getElementById("sidebarBackdrop");

    // The sidebar is not present on public/authentication pages.
    if (!sidebar || !toggleButton || !backdrop) {
        return;
    }

    /**
     * Open the mobile sidebar.
     */
    function openSidebar() {
        sidebar.classList.add("is-open");
        backdrop.classList.add("is-visible");
        document.body.classList.add("sidebar-open");

        backdrop.setAttribute("aria-hidden", "false");
        toggleButton.setAttribute("aria-expanded", "true");
    }

    /**
     * Close the mobile sidebar.
     */
    function closeSidebar() {
        sidebar.classList.remove("is-open");
        backdrop.classList.remove("is-visible");
        document.body.classList.remove("sidebar-open");

        backdrop.setAttribute("aria-hidden", "true");
        toggleButton.setAttribute("aria-expanded", "false");
    }

    // Toggle button.
    toggleButton.addEventListener("click", () => {
        const isOpen = sidebar.classList.contains("is-open");

        if (isOpen) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    // Close button inside the sidebar.
    if (closeButton) {
        closeButton.addEventListener("click", closeSidebar);
    }

    // Clicking outside the sidebar closes it.
    backdrop.addEventListener("click", closeSidebar);

    // Escape key closes the sidebar.
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeSidebar();
        }
    });

    // Close the mobile sidebar when returning to desktop width.
    window.addEventListener("resize", () => {
        if (window.innerWidth >= 1024) {
            closeSidebar();
        }
    });
}
