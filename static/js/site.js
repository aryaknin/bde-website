/* Interactions locales : navigation mobile, défilement et fenêtres de dialogue. */
(() => {
  const header = document.querySelector("[data-header]");
  const menuButton = document.querySelector("[data-menu-toggle]");
  const navigation = document.querySelector("#navigation");
  const mobileScreen = window.matchMedia("(max-width: 1250px)");

  const closeMenu = () => {
    header.classList.remove("menu-open");
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.querySelector("[data-menu-label]").textContent = "Menu";
  };

  if (header && menuButton && navigation) {
    header.classList.add("menu-ready");
    menuButton.hidden = false;
    menuButton.addEventListener("click", () => {
      const open = header.classList.toggle("menu-open");
      menuButton.setAttribute("aria-expanded", String(open));
      menuButton.querySelector("[data-menu-label]").textContent = open ? "Fermer" : "Menu";
    });
    navigation.addEventListener("click", (event) => {
      if (event.target.closest("a")) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && header.classList.contains("menu-open")) {
        closeMenu();
        menuButton.focus();
      }
    });
    mobileScreen.addEventListener("change", closeMenu);

    let previousY = window.scrollY;
    const updateNavigation = () => {
      const y = Math.max(0, window.scrollY);
      header.classList.toggle("is-scrolled", y > 12);
      if (y <= 12 || y < previousY || header.classList.contains("menu-open")) {
        header.classList.remove("is-hidden");
      } else if (y > 80 && y > previousY) {
        header.classList.add("is-hidden");
      }
      previousY = y;
    };
    updateNavigation();
    window.addEventListener("scroll", updateNavigation, { passive: true });
  }

  const welcome = document.querySelector("[data-welcome]");
  if (welcome && typeof welcome.showModal === "function") {
    const previousFocus = document.activeElement;
    welcome.querySelector("[data-dialog-close]").addEventListener("click", () => welcome.close());
    welcome.addEventListener("click", (event) => {
      const rect = welcome.getBoundingClientRect();
      const outside = event.clientX < rect.left || event.clientX > rect.right
        || event.clientY < rect.top || event.clientY > rect.bottom;
      if (event.target === welcome && outside) welcome.close();
    });
    welcome.addEventListener("close", () => {
      document.body.classList.remove("dialog-open");
      if (previousFocus instanceof HTMLElement) previousFocus.focus({ preventScroll: true });
    });
    welcome.showModal();
    document.body.classList.add("dialog-open");
  }

  document.querySelectorAll("[data-event-trigger]").forEach((trigger) => {
    const dialogId = trigger.getAttribute("aria-controls");
    const dialog = document.getElementById(dialogId);
    if (!dialog || typeof dialog.showModal !== "function") return;

    trigger.addEventListener("click", () => {
      dialog.showModal();
      document.body.classList.add("dialog-open");
    });

    dialog.querySelector("[data-event-dialog-close]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      const rect = dialog.getBoundingClientRect();
      const outside = event.clientX < rect.left || event.clientX > rect.right
        || event.clientY < rect.top || event.clientY > rect.bottom;
      if (event.target === dialog && outside) dialog.close();
    });
    dialog.addEventListener("close", () => {
      document.body.classList.remove("dialog-open");
      trigger.focus({ preventScroll: true });
    });
  });

  const adminEventDialog = document.querySelector("[data-admin-event-dialog]");
  const adminEventTriggers = document.querySelectorAll("[data-admin-event-open]");
  if (adminEventDialog && typeof adminEventDialog.showModal === "function") {
    let lastAdminTrigger = null;
    const openAdminDialog = (trigger = null) => {
      lastAdminTrigger = trigger;
      adminEventDialog.showModal();
      document.body.classList.add("dialog-open");
    };
    adminEventTriggers.forEach((trigger) => {
      trigger.addEventListener("click", () => openAdminDialog(trigger));
    });
    adminEventDialog.querySelectorAll("[data-admin-event-close]").forEach((button) => {
      button.addEventListener("click", () => adminEventDialog.close());
    });
    adminEventDialog.addEventListener("click", (event) => {
      const rect = adminEventDialog.getBoundingClientRect();
      const outside = event.clientX < rect.left || event.clientX > rect.right
        || event.clientY < rect.top || event.clientY > rect.bottom;
      if (event.target === adminEventDialog && outside) adminEventDialog.close();
    });
    adminEventDialog.addEventListener("close", () => {
      document.body.classList.remove("dialog-open");
      if (lastAdminTrigger) lastAdminTrigger.focus({ preventScroll: true });
    });
    if (new URLSearchParams(window.location.search).get("ajouter") === "1") {
      openAdminDialog();
    }
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reducedMotion) {
    window.addEventListener("pageshow", () => document.body.classList.remove("page-leaving"));
    document.addEventListener("click", (event) => {
      const link = event.target.closest("a[href]");
      if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey
          || event.ctrlKey || event.shiftKey || event.altKey || link.target || link.hasAttribute("download")) {
        return;
      }
      const destination = new URL(link.href, window.location.href);
      const sameDocument = destination.pathname === window.location.pathname
        && destination.search === window.location.search;
      if (destination.origin !== window.location.origin || sameDocument) return;
      event.preventDefault();
      document.body.classList.add("page-leaving");
      window.setTimeout(() => { window.location.href = destination.href; }, 170);
    });
  }
})();
