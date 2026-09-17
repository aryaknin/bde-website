/* Interactions locales : navigation mobile, défilement et fenêtres de dialogue. */
(() => {
  const header = document.querySelector("[data-header]");
  const menuButton = document.querySelector("[data-menu-toggle]");
  const navigation = document.querySelector("#navigation");
  const mobileScreen = window.matchMedia("(max-width: 1450px)");

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
      if (y <= 12 || y < previousY || header.classList.contains("menu-open")
          || header.contains(document.activeElement) || header.matches(":hover")) {
        header.classList.remove("is-hidden");
      } else if (y > 80 && y > previousY) {
        header.classList.add("is-hidden");
      }
      previousY = y;
    };
    updateNavigation();
    window.addEventListener("scroll", updateNavigation, { passive: true });
    header.addEventListener("focusin", () => header.classList.remove("is-hidden"));
    window.addEventListener("pageshow", () => {
      previousY = window.scrollY;
      header.classList.remove("is-hidden");
      updateNavigation();
    });
    window.addEventListener("pagehide", closeMenu);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        previousY = window.scrollY;
        header.classList.remove("is-hidden");
      }
    });
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
    // Ferme aussi le dialogue avant une restauration par le bouton Retour du navigateur.
    window.addEventListener("pagehide", () => {
      welcome.close();
      document.body.classList.remove("dialog-open");
    });
    welcome.showModal();
    document.body.classList.add("dialog-open");
  }

  const homeStats = document.querySelector("[data-home-stats-url]");
  if (homeStats) {
    let refreshing = false;
    let refreshTimer;
    const refreshHomeStats = async () => {
      if (document.hidden || refreshing) return;
      refreshing = true;
      try {
        const response = await fetch(homeStats.dataset.homeStatsUrl, { cache: "no-store" });
        if (!response.ok) return;
        const values = await response.json();
        homeStats.querySelectorAll("[data-home-stat]").forEach((stat) => {
          const key = stat.dataset.homeStat;
          const value = values[key];
          if (!Number.isInteger(value) || value < 0) return;
          stat.querySelector("dd").textContent = String(value);
          if (key === "members_count") {
            stat.querySelector("dt").textContent = value === 1 ? "Membre du BDE" : "Membres du BDE";
          } else if (key === "poles_count") {
            stat.querySelector("dt").textContent = value === 1 ? "Pôle" : "Pôles";
          }
        });
      } catch {
        // Conserve les chiffres rendus par Flask si le réseau est indisponible.
      } finally {
        refreshing = false;
      }
    };
    window.addEventListener("pageshow", () => {
      window.clearInterval(refreshTimer);
      refreshHomeStats();
      refreshTimer = window.setInterval(refreshHomeStats, 10000);
    });
    window.addEventListener("pagehide", () => window.clearInterval(refreshTimer));
    window.addEventListener("focus", refreshHomeStats);
    document.addEventListener("visibilitychange", refreshHomeStats);
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

  document.querySelectorAll("[data-member-trigger]").forEach((trigger) => {
    const dialog = document.getElementById(trigger.getAttribute("aria-controls"));
    if (!dialog || typeof dialog.showModal !== "function") return;
    trigger.addEventListener("click", () => {
      dialog.showModal();
      document.body.classList.add("dialog-open");
    });
    dialog.querySelector("[data-member-close]").addEventListener("click", () => dialog.close());
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

  const teamFilter = document.querySelector("[data-team-filter]");
  const teamCards = [...document.querySelectorAll("[data-team-card]")];
  const teamCount = document.querySelector("[data-team-count]");
  const teamLabel = document.querySelector("[data-team-label]");
  if (teamFilter && teamCards.length) {
    teamFilter.addEventListener("change", () => {
      const selectedRole = teamFilter.value;
      let visibleCount = 0;
      teamCards.forEach((card) => {
        const visible = !selectedRole || card.dataset.teamRole === selectedRole;
        card.hidden = !visible;
        if (visible) visibleCount += 1;
      });
      if (teamCount) teamCount.textContent = String(visibleCount);
      if (teamLabel) teamLabel.textContent = visibleCount === 1 ? "membre" : "membres";
    });
  }

  const adminTabs = [...document.querySelectorAll("[data-admin-tab]")];
  const adminPanels = [...document.querySelectorAll("[data-admin-panel]")];
  if (adminTabs.length && adminPanels.length) {
    const activateAdminTab = (name, updateUrl = false) => {
      adminTabs.forEach((tabButton) => {
        const active = tabButton.dataset.adminTab === name;
        tabButton.setAttribute("aria-selected", String(active));
        tabButton.tabIndex = active ? 0 : -1;
      });
      adminPanels.forEach((panel) => { panel.hidden = panel.dataset.adminPanel !== name; });
      if (updateUrl) {
        const url = new URL(window.location.href);
        name === "accounts" ? url.searchParams.delete("onglet") : url.searchParams.set("onglet", name);
        window.history.replaceState({}, "", url);
      }
    };
    adminTabs.forEach((tabButton) => {
      tabButton.addEventListener("click", () => activateAdminTab(tabButton.dataset.adminTab, true));
    });
    const requestedTab = new URLSearchParams(window.location.search).get("onglet");
    const availableTabs = adminTabs.map((tabButton) => tabButton.dataset.adminTab);
    activateAdminTab(availableTabs.includes(requestedTab) ? requestedTab : "accounts");
  }

})();
