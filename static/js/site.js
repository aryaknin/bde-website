/* Interactions locales : navigation mobile, défilement et fenêtres de dialogue. */
(() => {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let siteCursor = null;

  // Curseur visuel uniquement pour les souris : le curseur natif reste intact sur tactile et clavier.
  if (window.matchMedia("(hover: hover) and (pointer: fine)").matches && !reducedMotion.matches) {
    const cursor = document.createElement("div");
    siteCursor = cursor;
    cursor.className = "site-cursor";
    cursor.setAttribute("aria-hidden", "true");
    cursor.innerHTML = '<span class="site-cursor__dot"></span>';
    document.body.append(cursor);
    document.body.classList.add("has-custom-cursor");

    let frame;
    let x = -100;
    let y = -100;
    const paintCursor = () => {
      cursor.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      frame = undefined;
    };
    document.addEventListener("pointermove", (event) => {
      if (event.pointerType !== "mouse") return;
      x = event.clientX;
      y = event.clientY;
      if (!frame) frame = window.requestAnimationFrame(paintCursor);
    }, { passive: true });
    document.addEventListener("pointerover", (event) => {
      cursor.classList.toggle("is-interactive", Boolean(event.target.closest("a, button, input, select, textarea, summary, [role='button']")));
    });
    document.addEventListener("pointerdown", () => cursor.classList.add("is-pressed"));
    document.addEventListener("pointerup", () => cursor.classList.remove("is-pressed"));
    document.addEventListener("mouseleave", () => cursor.classList.add("is-hidden"));
    document.addEventListener("mouseenter", () => cursor.classList.remove("is-hidden"));
  }

  // Les <dialog> modaux sont rendus dans une couche spéciale du navigateur. Y déplacer
  // un élément fixed provoque un saut visuel : on emploie donc le curseur natif, stable,
  // dans les fenêtres et le curseur bleu revient dès leur fermeture.
  const updateDialogCursor = () => {
    const hasOpenDialog = [...document.querySelectorAll("dialog")].some((dialog) => dialog.open);
    document.body.classList.toggle("native-dialog-cursor", hasOpenDialog);
    siteCursor?.classList.toggle("is-hidden", hasOpenDialog);
  };
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("toggle", updateDialogCursor);
    dialog.addEventListener("close", updateDialogCursor);
  });

  // Une iframe Google est isolée du site : son curseur natif ne peut pas être remplacé.
  // On masque donc le curseur décoratif lorsqu’il entre dans le calendrier, sans le figer.
  document.querySelectorAll("iframe").forEach((frame) => {
    frame.addEventListener("pointerenter", () => siteCursor?.classList.add("is-hidden"));
    frame.addEventListener("pointerleave", () => siteCursor?.classList.remove("is-hidden"));
  });

  // Les blocs entrent dans le champ de vision plutôt que d’apparaître tous en même temps.
  const revealTargets = document.querySelectorAll(
    "main > .section > .container, main > .page-hero > .container, .event-card, .team-card, .product-card"
  );
  if (revealTargets.length) {
    revealTargets.forEach((target) => target.classList.add("reveal-on-scroll"));
    if (reducedMotion.matches || !("IntersectionObserver" in window)) {
      revealTargets.forEach((target) => target.classList.add("is-revealed"));
    } else {
      const observer = new IntersectionObserver((entries, currentObserver) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-revealed");
          currentObserver.unobserve(entry.target);
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -5%" });
      revealTargets.forEach((target) => observer.observe(target));
    }
  }

  // Parallaxe très limitée sur le hero : aucune animation continue ni mouvement sur tactile.
  const hero = document.querySelector(".hero");
  const heroImage = document.querySelector(".hero-image");
  if (hero && heroImage && window.matchMedia("(hover: hover) and (pointer: fine)").matches && !reducedMotion.matches) {
    let heroFrame;
    let shiftX = 0;
    let shiftY = 0;
    const paintHero = () => {
      heroImage.style.setProperty("--hero-shift-x", `${shiftX}px`);
      heroImage.style.setProperty("--hero-shift-y", `${shiftY}px`);
      heroFrame = undefined;
    };
    hero.addEventListener("pointermove", (event) => {
      const bounds = hero.getBoundingClientRect();
      shiftX = ((event.clientX - bounds.left) / bounds.width - .5) * 14;
      shiftY = ((event.clientY - bounds.top) / bounds.height - .5) * 10;
      if (!heroFrame) heroFrame = window.requestAnimationFrame(paintHero);
    }, { passive: true });
    hero.addEventListener("pointerleave", () => {
      shiftX = 0;
      shiftY = 0;
      if (!heroFrame) heroFrame = window.requestAnimationFrame(paintHero);
    });
  }

  // Squelettes pour les images chargées après le HTML (portraits et produits en lazy-loading).
  document.querySelectorAll("img[loading='lazy']").forEach((image) => {
    const shell = image.closest(".product-card__visual, .team-card__button, .member-dialog__portrait, .product-detail__visual, .cart-line__image");
    if (!shell) return;
    const finish = () => {
      shell.classList.remove("is-image-loading");
      shell.classList.add("is-image-loaded");
    };
    shell.classList.add("is-image-loading");
    if (image.complete) finish();
    else {
      image.addEventListener("load", finish, { once: true });
      image.addEventListener("error", finish, { once: true });
    }
  });

  // Reflet directionnel très discret pour les cartes survolées.
  if (window.matchMedia("(hover: hover) and (pointer: fine)").matches && !reducedMotion.matches) {
    document.querySelectorAll(".event-card--interactive, .product-card").forEach((card) => {
      card.addEventListener("pointermove", (event) => {
        const bounds = card.getBoundingClientRect();
        card.style.setProperty("--card-glow-x", `${((event.clientX - bounds.left) / bounds.width) * 100}%`);
        card.style.setProperty("--card-glow-y", `${((event.clientY - bounds.top) / bounds.height) * 100}%`);
      }, { passive: true });
    });
  }

  const header = document.querySelector("[data-header]");
  const menuButton = document.querySelector("[data-menu-toggle]");
  const menuBackdrop = document.querySelector("[data-menu-backdrop]");
  const navigation = document.querySelector("#navigation");
  const mobileScreen = window.matchMedia("(max-width: 1450px)");

    const closeMenu = () => {
      header.classList.remove("menu-open");
      navigation.style.removeProperty("transform");
      navigation.style.removeProperty("opacity");
      navigation.style.removeProperty("visibility");
      menuButton.setAttribute("aria-expanded", "false");
      menuButton.querySelector("[data-menu-label]").textContent = "Menu";
      menuBackdrop.hidden = true;
    };

  if (header && menuButton && navigation) {
    header.classList.add("menu-ready");
    menuButton.hidden = false;
    menuButton.addEventListener("click", () => {
      const open = header.classList.toggle("menu-open");
      menuButton.setAttribute("aria-expanded", String(open));
      menuButton.querySelector("[data-menu-label]").textContent = open ? "Fermer" : "Menu";
      menuBackdrop.hidden = !open;
      if (open) navigation.querySelector("a")?.focus({ preventScroll: true });
    });
    menuBackdrop.addEventListener("click", () => {
      closeMenu();
      menuButton.focus({ preventScroll: true });
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

  const readingProgress = document.querySelector("[data-reading-progress]");
  if (readingProgress) {
    let progressFrame;
    const updateReadingProgress = () => {
      const maximum = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      const progress = Math.min(1, Math.max(0, window.scrollY / maximum));
      readingProgress.style.transform = `scaleX(${progress})`;
      progressFrame = undefined;
    };
    const requestProgressUpdate = () => {
      if (!progressFrame) progressFrame = window.requestAnimationFrame(updateReadingProgress);
    };
    updateReadingProgress();
    window.addEventListener("scroll", requestProgressUpdate, { passive: true });
    window.addEventListener("resize", requestProgressUpdate, { passive: true });
    window.addEventListener("pageshow", requestProgressUpdate);
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
    let statsAreVisible = false;
    const animateNumber = (output, value) => {
      const previous = Number.parseInt(output.textContent, 10);
      const from = Number.isFinite(previous) ? previous : 0;
      if (reducedMotion.matches || from === value) {
        output.textContent = String(value);
        return;
      }
      const animationId = String(Number(output.dataset.countAnimation || "0") + 1);
      output.dataset.countAnimation = animationId;
      const startedAt = performance.now();
      const duration = Math.min(900, 350 + Math.abs(value - from) * 7);
      const render = (now) => {
        if (output.dataset.countAnimation !== animationId) return;
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - (1 - progress) ** 3;
        output.textContent = String(Math.round(from + (value - from) * eased));
        if (progress < 1) window.requestAnimationFrame(render);
      };
      window.requestAnimationFrame(render);
    };
    const setHomeStat = (stat, value, animate = false) => {
      if (!Number.isInteger(value) || value < 0) return;
      const output = stat.querySelector("dd");
      if (animate && statsAreVisible) animateNumber(output, value);
      else output.textContent = String(value);
      const key = stat.dataset.homeStat;
      if (key === "members_count") {
        stat.querySelector("dt").textContent = value === 1 ? "Membre du BDE" : "Membres du BDE";
      } else if (key === "poles_count") {
        stat.querySelector("dt").textContent = value === 1 ? "Pôle" : "Pôles";
      }
    };
    const launchCounters = () => {
      if (statsAreVisible) return;
      statsAreVisible = true;
      homeStats.querySelectorAll("[data-home-stat]").forEach((stat) => {
        const value = Number.parseInt(stat.querySelector("dd").textContent, 10);
        stat.querySelector("dd").textContent = "0";
        setHomeStat(stat, value, true);
      });
    };
    if (reducedMotion.matches || !("IntersectionObserver" in window)) launchCounters();
    else {
      const statsObserver = new IntersectionObserver((entries, observer) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        launchCounters();
        observer.disconnect();
      }, { threshold: .35 });
      statsObserver.observe(homeStats);
    }
    const refreshHomeStats = async () => {
      if (document.hidden || refreshing) return;
      refreshing = true;
      try {
        const response = await fetch(homeStats.dataset.homeStatsUrl, { cache: "no-store" });
        if (!response.ok) return;
        const values = await response.json();
        homeStats.querySelectorAll("[data-home-stat]").forEach((stat) => {
          setHomeStat(stat, values[stat.dataset.homeStat], true);
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
