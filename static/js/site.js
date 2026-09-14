/* Interactions locales : navigation mobile, défilement et bienvenue. */
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
})();
