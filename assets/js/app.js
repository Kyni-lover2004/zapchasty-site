/* PartStack — клиентская логика: маршрутизация, поиск, фильтры, корзина. */
(function () {
  "use strict";

  const DATA = window.CATALOG_DATA;
  const CATEGORIES = DATA.CATEGORIES;
  const PRODUCTS = DATA.PRODUCTS;
  const MODELS = DATA.MODELS;
  const CONTACTS = DATA.CONTACTS;
  const SOCIAL_LINKS = DATA.SOCIAL_LINKS;

  const CART_KEY = "z62_cart_v1";

  const app = document.getElementById("app");
  const categoryById = new Map(CATEGORIES.map((category) => [category.id, category]));
  const productById = new Map(PRODUCTS.map((product) => [product.id, product]));
  const productBySlug = new Map(PRODUCTS.map((product) => [product.slug, product]));

  let cart = readCart();
  let toastTimer = null;
  const favorites = readFavorites();

  /* ---------- Утилиты ---------- */

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatPrice(value) {
    return new Intl.NumberFormat("ru-RU").format(value) + " ₽";
  }

  function plural(count, forms) {
    const absolute = Math.abs(count) % 100;
    const last = absolute % 10;
    if (absolute > 10 && absolute < 20) return forms[2];
    if (last > 1 && last < 5) return forms[1];
    if (last === 1) return forms[0];
    return forms[2];
  }

  function productImage(product) {
    if (product.images?.length) return product.images[0];
    const category = categoryById.get(product.category);
    return `assets/img/${category ? category.icon : "tool"}.svg`;
  }

  function categoryName(id) {
    const category = categoryById.get(id);
    return category ? category.name : "";
  }

  /* ---------- Корзина ---------- */

  function readCart() {
    try {
      const stored = JSON.parse(localStorage.getItem(CART_KEY) || "[]");
      if (!Array.isArray(stored)) return [];
      return stored
        .filter((item) => item && productById.has(Number(item.id)) && Number.isFinite(Number(item.qty)) && Number(item.qty) >= 1 && productById.get(Number(item.id)).stock > 0)
        .map((item) => ({ id: Number(item.id), qty: Math.min(Math.floor(Number(item.qty)), productById.get(Number(item.id)).stock) }));
    } catch (error) {
      return [];
    }
  }

  function saveCart() {
    try {
      localStorage.setItem(CART_KEY, JSON.stringify(cart));
    } catch (error) {
      showToast("Не удалось сохранить корзину в этом браузере");
    }
    updateCartBadge();
    syncShoppingControls();
  }

  function cartItems() {
    return cart
      .map((item) => {
        const product = productById.get(item.id);
        return product ? { product, qty: item.qty } : null;
      })
      .filter(Boolean);
  }

  function cartCount() {
    return cart.reduce((sum, item) => sum + item.qty, 0);
  }

  function cartTotal() {
    return cartItems().reduce((sum, item) => sum + item.product.price * item.qty, 0);
  }

  function addToCart(id, qty) {
    const product = productById.get(id);
    if (!product || product.stock <= 0) return;
    const existing = cart.find((item) => item.id === id);
    const currentQty = existing ? existing.qty : 0;
    const nextQty = Math.min(currentQty + qty, product.stock);
    if (nextQty === currentQty) {
      showToast(`В наличии только ${product.stock} ${plural(product.stock, ["шт.", "шт.", "шт."])}`);
      return;
    }
    if (existing) existing.qty = nextQty;
    else cart.push({ id: id, qty: nextQty });
    saveCart();
    showToast(`«${product.name}» — в корзине`);
  }

  function setCartQty(id, qty) {
    const product = productById.get(id);
    const item = cart.find((entry) => entry.id === id);
    if (!product || !item) return;
    if (qty <= 0) {
      cart = cart.filter((entry) => entry.id !== id);
    } else {
      item.qty = Math.min(qty, product.stock);
    }
    saveCart();
  }

  function removeFromCart(id) {
    cart = cart.filter((item) => item.id !== id);
    saveCart();
  }

  function clearCart() {
    cart = [];
    saveCart();
  }

  function updateCartBadge() {
    const count = cartCount();
    document.querySelectorAll("[data-cart-count]").forEach((node) => {
      node.textContent = String(count);
    });
  }

  /* ---------- Тосты ---------- */

  function showToast(message) {
    const toast = document.querySelector("[data-toast]");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.classList.remove("is-visible");
    }, 2800);
  }

  /* ---------- Иконки ---------- */

  const ICONS = {
    arrow: '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 7h9M8 4l3 3-3 3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    plus: '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
    pin: '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.5a5 5 0 0 1 5 5c0 3.6-5 8-5 8s-5-4.4-5-8a5 5 0 0 1 5-5Z" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="8" cy="6.5" r="1.7" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
    check: '<svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><path d="m5 13.5 5 5L21 7.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    copy: '<svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M10.5 3.5v-1a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
    print: '<svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 5.5v-3h7v3M4.5 11.5h-2v-6h11v6h-2" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><rect x="4.5" y="9.5" width="7" height="4.5" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
    vk: '<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M12.8 18.2c-6 0-9.4-4.1-9.5-11h3c.1 5 2.3 7.1 4 7.5V7.2h2.8v4.3c1.7-.2 3.5-2.1 4.1-4.3h2.8c-.5 2.6-2.4 4.5-3.8 5.3 1.4.6 3.6 2.3 4.4 5.7h-3.1c-.6-1.9-2.2-3.4-4.4-3.6v3.6h-.3Z" fill="currentColor"/></svg>',
    telegram: '<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M21.5 4.3 18.3 19c-.2 1-.9 1.3-1.8.8l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.3-4.9 8.9-8c.4-.3-.1-.5-.6-.2L6.9 13.2 2 11.7c-1-.3-1-1 .2-1.5L20 3.4c.9-.3 1.7.2 1.5.9Z" fill="currentColor"/></svg>',
  };

  /* ---------- Маршрутизация ---------- */

  function getRoute() {
    const raw = location.hash.startsWith("#") ? location.hash.slice(1) : "/";
    const [pathPart, queryPart] = raw.split("?");
    let path = pathPart || "/";
    if (path.length > 1) path = path.replace(/\/+$/, "");
    return { path: path, query: new URLSearchParams(queryPart || "") };
  }

  function navigate(path) {
    if (location.hash === "#" + path) {
      render();
      return;
    }
    location.hash = path;
  }

  function render() {
    const route = getRoute();
    const path = route.path;

    app.classList.remove("page");
    void app.offsetWidth;

    if (path === "/models") {
      renderModels();
    } else if (path === "/favorites") {
      renderFavorites();
    } else if (path === "/") {
      renderHome();
    } else if (path === "/catalog") {
      renderCatalog(route, false);
    } else if (path === "/search") {
      renderCatalog(route, true);
    } else if (path.startsWith("/product/")) {
      const slug = path.slice("/product/".length);
      const product = productBySlug.get(slug);
      if (product) renderProduct(product);
      else renderNotFound("Товар не найден");
    } else if (path === "/cart") {
      renderCart();
    } else if (path === "/how-to-order") {
      renderOrderGuide();
    } else if (path === "/checkout") {
      renderCheckout();
    } else if (path === "/orders" || path.startsWith("/order/")) {
      renderCheckout();
    } else {
      renderNotFound("Страница не найдена");
    }

    app.classList.add("page");
    syncShoppingControls();
    document.querySelector("[data-suggestions]").hidden = true;
    window.scrollTo(0, 0);
    syncHeaderSearch(route);
    updateActiveNav(route);
  }

  function syncHeaderSearch(route) {
    const input = document.querySelector("[data-search-form] input[name='q']");
    if (!input) return;
    input.value = route.path === "/search" ? route.query.get("q") || "" : "";
  }

  function updateActiveNav(route) {
    const path = route.path;
    const navKey =
      path === "/"
        ? "home"
        : path === "/catalog" || path === "/search"
          ? "catalog"
          : path === "/cart" || path === "/checkout" || path.startsWith("/order/")
            ? "cart"
            : "";
    document.querySelectorAll(".mobilenav a").forEach((link) => {
      link.classList.toggle("is-active", link.dataset.nav === navKey);
    });
  }

  function setActiveCat(categoryId) {
    document.querySelectorAll("#catnav a").forEach((link) => {
      link.classList.toggle("is-active", link.dataset.cat === (categoryId || ""));
    });
  }

  /* ---------- Общие блоки ---------- */

  function renderCatnav() {
    const nav = document.getElementById("catnav");
    if (!nav) return;
    nav.innerHTML =
      '<a href="#/catalog" data-cat="all">Все запчасти</a>' +
      CATEGORIES.map(
        (category) =>
          `<a href="#/search?cat=${category.id}" data-cat="${category.id}">${escapeHtml(category.name)}</a>`
      ).join("");
  }

  function renderFooterCategories() {
    const list = document.getElementById("footer-categories");
    if (!list) return;
    list.innerHTML = CATEGORIES.map(
      (category) => `<li><a href="#/search?cat=${category.id}">${escapeHtml(category.name)}</a></li>`
    ).join("");
  }

  function countByCategory(categoryId) {
    return PRODUCTS.filter((product) => product.category === categoryId).length;
  }

  function categoryCard(category) {
    return `
      <a class="category" href="#/search?cat=${category.id}">
        <span class="category__icon"><img src="assets/img/${category.icon}.svg" alt="" width="30" height="30" loading="lazy"></span>
        <span>
          <span class="category__name">${escapeHtml(category.name)}</span>
          <span class="category__count">${countByCategory(category.id)} ${plural(countByCategory(category.id), ["позиция", "позиции", "позиций"])}</span>
        </span>
        <span class="category__arrow">${ICONS.arrow}</span>
      </a>`;
  }

  function productCard(product) {
    const category = categoryById.get(product.category);
    const isOut = product.stock <= 0;
    const discount = product.oldPrice
      ? Math.round((1 - product.price / product.oldPrice) * 100)
      : 0;
    const badges = [];
    if (product.badge) badges.push(`<span class="badge badge--hit">${escapeHtml(product.badge)}</span>`);
    if (discount >= 5) badges.push(`<span class="badge badge--sale">−${discount}%</span>`);
    if (isOut) badges.push('<span class="badge badge--out">Нет в наличии</span>');
    const meta =
      product.brand === product.device
        ? product.brand
        : `${product.brand} · ${product.device}`;
    const stockText = isOut ? "Нет" : `${product.stock} шт.`;
    return `
      <article class="card${isOut ? " card--out" : ""}">
        <a class="card__media" href="#/product/${product.slug}" aria-label="${escapeHtml(product.name)}">
          <img src="${productImage(product)}" alt="" width="200" height="200" loading="lazy">
          <span class="card__badges">${badges.join("")}</span>
        </a>
        <div class="card__body">
          ${renderFavoriteButton(product)}
          <p class="card__meta-top">${escapeHtml(meta)}</p>
          <h3 class="card__title"><a href="#/product/${product.slug}">${escapeHtml(product.name)}</a></h3>
          <p class="card__sub">${escapeHtml(product.subtitle)}</p>
          <div class="card__info">
            <span>${escapeHtml(product.part)}</span>
            <span class="card__stock">${stockText}</span>
          </div>
          <div class="card__foot">
            <div class="price">
              ${product.oldPrice ? `<s>${formatPrice(product.oldPrice)}</s>` : ""}
              <b>${formatPrice(product.price)}</b>
            </div>
            <button class="card__add" type="button" data-add="${product.id}" aria-label="Добавить «${escapeHtml(product.name)}» в корзину" ${isOut ? "disabled" : ""}>
              ${isOut ? "Нет в наличии" : "В корзину"}
            </button>
          </div>
        </div>
      </article>`;
  }

  /** Рисует разнесённые слои и связывает детали с разделами каталога. */
  function blueprintSvg() {
    const parts = [
      { label: "Защитное стекло", category: "glass", x: 1, y: 94, line: "M13 94H30" },
      { label: "Дисплей", category: "displays", x: 1, y: 188, line: "M13 188H47" },
      { label: "Камеры", category: "cameras", x: 188, y: 65, line: "M200 65H229L243 79" },
      { label: "Основная плата", category: "boards", x: 372, y: 82, line: "M360 82H344L327 99" },
      { label: "Компоненты плат", category: "board-components", x: 372, y: 128, line: "M360 128H324L303 110" },
      { label: "Аккумулятор", category: "batteries", x: 372, y: 184, line: "M360 184H319" },
      { label: "Шлейф", category: "flex", x: 188, y: 224, line: "M200 224H324" },
      { label: "Нижние платы", category: "lower-boards", x: 188, y: 278, line: "M200 278H238" },
      { label: "Разъём зарядки", category: "charging", x: 280, y: 332, line: "M280 320V307" },
      { label: "Динамик", category: "speakers", x: 372, y: 266, line: "M360 266H342L330 288" },
      { label: "Корпус и крышка", category: "covers", x: 542, y: 267, line: "M530 267H516" },
    ];
    const annotations = parts.map(({ x, y, line, category }, index) => `
      <path class="bp-leader" d="${line}"/>
      <a class="bp-marker" href="#/search?cat=${category}" tabindex="-1">
        <circle class="bp-pin" cx="${x}" cy="${y}" r="12"/>
        <text class="bp-number" x="${x}" y="${y + 4}">${index + 1}</text>
      </a>`).join("");
    return `
      <figure class="blueprint" aria-label="Схема разбора смартфона">
        <div class="blueprint__head"><span>Схема разбора · PartStack</span><b>Рязань</b></div>
        <div class="blueprint__art">
          <svg viewBox="-25 0 599 360" aria-hidden="true">
            <defs>
              <pattern id="bp-grid" width="16" height="16" patternUnits="userSpaceOnUse">
                <path d="M16 0H0V16" fill="none" stroke="#dfebf6"/>
              </pattern>
              <pattern id="bp-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <path d="M0 0V5" stroke="#9dbdde" fill="none"/>
              </pattern>
            </defs>
            <rect x="-25" width="599" height="360" fill="url(#bp-grid)"/>
            <g class="bp-layer-name">
              <text x="92" y="28">ПЕРЕДНИЙ МОДУЛЬ</text>
              <text x="280" y="28">ВНУТРЕННИЕ УЗЛЫ</text>
              <text x="461" y="28">ЗАДНЯЯ КРЫШКА</text>
            </g>
            <path class="bp-axis" d="M-15 200H564M92 41V344M280 41V344M461 41V344"/>
            <g class="bp-shell" transform="translate(-25 0)">
              <rect x="55" y="58" width="124" height="251" rx="21"/>
              <rect x="64" y="67" width="106" height="233" rx="16" class="bp-axis"/>
              <rect class="bp-panel" x="72" y="76" width="90" height="215" rx="10"/>
              <path d="M106 84h22m-37 53 37-38m-28 58 43-44" stroke-linecap="round"/>
              <path class="bp-copper" d="M122 291v13h16v16h-24v-16h-9v-13z"/>
              <path d="M120 311h12m-12 4h12"/>
            </g>
            <g class="bp-shell">
              <rect x="222" y="49" width="116" height="270" rx="20"/>
              <rect x="228" y="55" width="104" height="258" rx="15" class="bp-axis"/>
              <path class="bp-panel" d="M233 63h94v66h-21v10h-72v-22h18V97h-19z"/>
              <rect class="bp-panel" x="233" y="69" width="43" height="25" rx="5"/>
              <circle class="bp-chip" cx="244" cy="81" r="7"/>
              <circle class="bp-chip" cx="264" cy="81" r="7"/>
              <circle cx="244" cy="81" r="3"/>
              <circle cx="264" cy="81" r="3"/>
              <rect class="bp-chip" x="280" y="94" width="23" height="20" rx="2"/>
              <path d="M283 91v3m5-3v3m5-3v3m5-3v3m-15 20v3m5-3v3m5-3v3m5-3v3M276 98h4m-4 5h4m-4 5h4m23-5h8v16h11m-46 3h21m-30 6h29"/>
              <path class="bp-chip" d="M282 72h9v9h-9zM307 75h13v9h-13zM309 91h10v7h-10zM256 104h12v7h-12z"/>
              <rect class="bp-panel" x="240" y="148" width="79" height="113" rx="8"/>
              <rect x="247" y="155" width="65" height="99" rx="4" class="bp-axis"/>
              <path class="bp-power" d="M284 177l-15 25h12l-6 18 17-26h-12l4-17z"/>
              <path class="bp-copper" d="M319 133h8v125h-15v17h-8v-25h15z"/>
              <path d="M323 139v111m-4 4h8"/>
              <path class="bp-panel" d="M236 270h69v7h10v22h-18v7h-45v-7h-16z"/>
              <path d="M245 277h14v11h-14zm22 0h10v7h-10zm-23 16h9m11 0h8m16-14h15m-15 6h14"/>
              <rect class="bp-chip" x="270" y="298" width="20" height="10" rx="2"/>
              <path d="M275 303h10"/>
              <rect x="316" y="279" width="15" height="20" rx="3" fill="url(#bp-hatch)"/>
              <circle cx="233" cy="148" r="2"/><circle cx="327" cy="148" r="2"/>
              <circle cx="232" cy="263" r="2"/><circle cx="329" cy="263" r="2"/>
            </g>
            <g class="bp-shell" transform="translate(14 0)">
              <rect x="392" y="58" width="110" height="251" rx="21"/>
              <rect x="399" y="65" width="96" height="237" rx="15" class="bp-axis"/>
              <rect class="bp-panel" x="405" y="72" width="42" height="64" rx="9"/>
              <circle cx="418" cy="88" r="7"/><circle cx="432" cy="104" r="7"/><circle cx="418" cy="119" r="7"/>
              <path d="M433 85h4m-4 34h4"/>
              <path d="M443 204h8m-4-4v8" stroke-linecap="round"/>
            </g>
            ${annotations}
          </svg>
        </div>
        <ul class="blueprint__parts" aria-label="Детали на схеме">
          ${parts.map(({ label, category }, index) => `
            <li>
              <a href="#/search?cat=${category}">
                <span aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>${label}
              </a>
            </li>`).join("")}
        </ul>
        <figcaption>Выберите деталь, чтобы открыть раздел каталога</figcaption>
      </figure>`;
  }

  /* ---------- Главная ---------- */

  function renderHome() {
    document.title = "PartStack — запчасти для ремонта телефонов в Рязани";
    setActiveCat(null);
    const featured = PRODUCTS.filter((product) => product.featured).slice(0, 8);
    app.innerHTML = `
      <section class="hero">
        <div class="container hero__in">
          <div>
            <p class="eyebrow">Рязань · запчасти для ремонта</p>
            <h1>Найдите деталь <span class="mark">по модели</span> или артикулу</h1>
            <p class="hero__lead">Дисплеи, аккумуляторы, шлейфы и инструмент. Подберите совместимую деталь и проверьте остаток перед заказом.</p><a class="model-entry" href="#/models">Подобрать точно по модели ${ICONS.arrow}</a>
            <form class="finder" data-finder>
              <select name="cat" aria-label="Категория запчастей">
                <option value="">Все категории</option>
                ${CATEGORIES.map(
                  (category) =>
                    `<option value="${category.id}">${escapeHtml(category.name)}</option>`
                ).join("")}
              </select>
              <input name="q" type="search" placeholder="iPhone 11, Redmi Note 12, DSP-IP11…" aria-label="Модель телефона или артикул" autocomplete="off">
              <button class="btn btn--primary" type="submit">Найти</button>
            </form>
            <div class="hero__chips">
              <span>Часто ищут</span>
              ${MODELS.map(
                (model) =>
                  `<a href="#/search?q=${encodeURIComponent(model)}">${escapeHtml(model)}</a>`
              ).join("")}
            </div>
          </div>
          ${blueprintSvg()}
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="section__head">
            <div>
              <p class="eyebrow">Каталог</p>
              <h2>Что нужно отремонтировать?</h2>
              <p>Запчасти, комплектующие для плат и инструмент.</p>
            </div>
            <a class="section__link" href="#/catalog">Все запчасти ${ICONS.arrow}</a>
          </div>
          <div class="categories">
            ${CATEGORIES.map(categoryCard).join("")}
          </div>
        </div>
      </section>

      <section class="section section--mist">
        <div class="container">
          <div class="section__head">
            <div>
              <p class="eyebrow">Наличие</p>
              <h2>В наличии в Рязани</h2>
              <p>Демонстрационный каталог: цены и остатки приведены для примера.</p>
            </div>
            <a class="section__link" href="#/catalog">Смотреть каталог ${ICONS.arrow}</a>
          </div>
          <div class="product-grid">
            ${featured.map(productCard).join("")}
          </div>
        </div>
      </section>

      <section class="pickup">
        <div class="container pickup__in">
          <div>
            <p class="eyebrow">Самовывоз</p>
            <h2>Заберите заказ в центре Рязани</h2>
            <div class="pickup__steps">
              <div class="pickup__step">
                <b>01</b>
                <span>Найдите деталь по модели или артикулу</span>
              </div>
              <div class="pickup__step">
                <b>02</b>
                <span>Добавьте в корзину и оформите заказ</span>
              </div>
              <div class="pickup__step">
                <b>03</b>
                <span>Дождитесь подтверждения и заберите заказ</span>
              </div>
            </div>
          </div>
          <div class="pickup__card">
            <span class="mono">Пункт выдачи</span>
            <p class="pickup__address">${escapeHtml(CONTACTS.addressFull)}</p>
            <p>${escapeHtml(CONTACTS.hours)}</p>
            <p>Наличными или картой при получении</p>
            <p><a href="#/how-to-order">Как заказать</a></p>
            ${CONTACTS.phoneHref ? `<a href="tel:${escapeHtml(CONTACTS.phoneHref)}">${escapeHtml(CONTACTS.phone)}</a>` : ""}
          </div>
        </div>
      </section>`;

    const finder = app.querySelector("[data-finder]");
    finder.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(finder);
      const query = String(formData.get("q") || "").trim();
      const category = String(formData.get("cat") || "");
      const params = new URLSearchParams();
      if (query) params.set("q", query);
      if (category) params.set("cat", category);
      if (query || category) navigate("/search?" + params.toString());
      else navigate("/catalog");
    });
  }

  /* ---------- Каталог и поиск ---------- */

  const SYNONYMS = {
    акб: ["аккумулятор", "батарея"],
    аккумулятор: ["акб", "батарея"],
    батарея: ["акб", "аккумулятор"],
    экран: ["дисплей", "тачскрин"],
    дисплей: ["экран", "тачскрин"],
    тачскрин: ["дисплей", "экран"],
    зарядка: ["разъем", "шлейф"],
    разъем: ["зарядка"],
    стекло: ["стекла", "пленка"],
    пленка: ["стекло"],
    крышка: ["корпус"],
    корпус: ["крышка"],
    камера: ["камеры"],
    шлейф: ["flex"],
    инструмент: ["отвертка", "пинцет", "паяльная"],
  };

  function normalize(value) {
    return String(value)
      .toLowerCase()
      .replace(/ё/g, "е")
      .replace(/[^a-zа-я0-9]+/g, " ")
      .trim();
  }

  function tokenize(query) {
    return normalize(query).split(" ").filter(Boolean);
  }

  function variantsFor(token) {
    return [token].concat(SYNONYMS[token] || []);
  }

  function scoreProduct(product, tokens) {
    const category = categoryById.get(product.category);
    const fields = {
      part: normalize(product.part),
      name: normalize(product.name),
      device: normalize([product.device].concat(product.compat).join(" ")),
      brand: normalize(product.brand),
      category: normalize((category ? category.name : "") + " " + product.subtitle),
      compact: normalize(
        [product.part, product.name, product.device, product.brand, product.compat.join(" ")].join(" ")
      ).replace(/ /g, ""),
    };
    let total = 0;
    for (const token of tokens) {
      let best = 0;
      for (const variant of variantsFor(token)) {
        let score = 0;
        if (fields.part.includes(variant)) score = Math.max(score, 14);
        if (fields.name.includes(variant)) score = Math.max(score, 9);
        if (fields.device.includes(variant)) score = Math.max(score, 7);
        if (fields.brand.includes(variant)) score = Math.max(score, 4);
        if (fields.category.includes(variant)) score = Math.max(score, 2);
        const compact = variant.replace(/ /g, "");
        if (compact && fields.compact.includes(compact)) score = Math.max(score, 6);
        best = Math.max(best, score);
      }
      if (!best) return 0;
      total += best;
    }
    return total;
  }

  function filtersFromQuery(query) {
    const categories = (query.get("cat") || "")
      .split(",")
      .filter((id) => categoryById.has(id));
    const brands = (query.get("brand") || "")
      .split(",")
      .filter(Boolean);
    const min = query.get("min") || "";
    const max = query.get("max") || "";
    const sort = ["relevance", "price-asc", "price-desc", "stock"].includes(query.get("sort") || "")
      ? query.get("sort")
      : "relevance";
    return {
      q: (query.get("q") || "").trim(),
      model: query.get("model") || "",
      cat: categories,
      brand: brands,
      stock: query.get("stock") === "1",
      min: /^\d+$/.test(min) ? min : "",
      max: /^\d+$/.test(max) ? max : "",
      sort: sort,
    };
  }

  function filterProducts(state) {
    const tokens = tokenize(state.q);
    let scored = PRODUCTS.map((product, index) => ({
      product: product,
      index: index,
      score: tokens.length ? scoreProduct(product, tokens) : 0,
    }));
    if (tokens.length) scored = scored.filter((item) => item.score > 0);
    scored = scored.filter((item) => {
      const product = item.product;
      if (state.model && !product.compat.includes(state.model)) return false;
      if (state.cat.length && !state.cat.includes(product.category)) return false;
      if (state.brand.length && !state.brand.includes(product.brand)) return false;
      if (state.stock && product.stock <= 0) return false;
      if (state.min !== "" && product.price < Number(state.min)) return false;
      if (state.max !== "" && product.price > Number(state.max)) return false;
      return true;
    });
    if (state.sort === "price-asc") {
      scored.sort((a, b) => a.product.price - b.product.price || a.index - b.index);
    } else if (state.sort === "price-desc") {
      scored.sort((a, b) => b.product.price - a.product.price || a.index - b.index);
    } else if (state.sort === "stock") {
      scored.sort((a, b) => b.product.stock - a.product.stock || a.index - b.index);
    } else {
      scored.sort((a, b) => b.score - a.score || a.index - b.index);
    }
    return scored.map((item) => item.product);
  }

  function pageTitle(state, isSearch) {
    if (state.model) return `Запчасти для ${state.model}`;
    if (state.q) return `Поиск: «${state.q}»`;
    if (state.cat.length === 1) return categoryName(state.cat[0]);
    if (isSearch) return "Поиск запчастей";
    return "Каталог запчастей";
  }

  function pageSubtitle(state, isSearch) {
    if (state.q) return "Совпадения по названию, модели телефона и артикулу.";
    if (state.cat.length === 1) {
      const category = categoryById.get(state.cat[0]);
      return category ? category.desc : "Все позиции в наличии в Рязани.";
    }
    if (isSearch) return "Введите модель телефона или артикул в строке поиска.";
    return "Все запчасти с самовывозом в Рязани. Выберите категорию или воспользуйтесь поиском.";
  }

  function buildUrl(base, state) {
    const params = new URLSearchParams();
    if (state.q) params.set("q", state.q);
    if (state.model) params.set("model", state.model);
    if (state.cat.length) params.set("cat", state.cat.join(","));
    if (state.brand.length) params.set("brand", state.brand.join(","));
    if (state.stock) params.set("stock", "1");
    if (state.min !== "") params.set("min", state.min);
    if (state.max !== "") params.set("max", state.max);
    if (state.sort !== "relevance") params.set("sort", state.sort);
    const query = params.toString();
    return base + (query ? "?" + query : "");
  }

  function brandCount(brand) {
    return PRODUCTS.filter((product) => product.brand === brand).length;
  }

  function renderCatalog(route, isSearch) {
    const state = filtersFromQuery(route.query);
    const base = isSearch ? "/search" : "/catalog";
    document.title = `${pageTitle(state, isSearch)} — PartStack`;
    setActiveCat(state.cat.length === 1 ? state.cat[0] : "all");

    const brands = Array.from(new Set(PRODUCTS.map((product) => product.brand))).sort((a, b) =>
      a.localeCompare(b, "ru")
    );

    app.innerHTML = `
      <section class="pagehead">
        <div class="container pagehead__in">
          <nav class="crumbs" aria-label="Хлебные крошки">
            <a href="#/">Главная</a><span>/</span>
            <a href="#/catalog">Каталог</a>
            ${isSearch ? '<span>/</span><span>Поиск</span>' : ""}
          </nav>
          <h1 data-page-title>${escapeHtml(pageTitle(state, isSearch))}</h1>
          <p class="pagehead__sub" data-page-sub>${escapeHtml(pageSubtitle(state, isSearch))}</p>
        </div>
      </section>

      <div class="catalog">
        <div class="container catalog__layout">
          <aside class="filters" data-filters aria-label="Фильтры">
            <div class="filters__head">
              <h2>Фильтры</h2>
              <button class="filters__reset" type="button" data-reset-filters>Сбросить</button>
            </div>

            <div class="filters__group">
              <h3>Категория</h3>
              ${CATEGORIES.map(
                (category) => `
                <label class="check">
                  <input type="checkbox" name="cat" value="${category.id}" ${state.cat.includes(category.id) ? "checked" : ""}>
                  <span>${escapeHtml(category.name)}</span>
                  <span class="check__count">${countByCategory(category.id)}</span>
                </label>`
              ).join("")}
            </div>

            <div class="filters__group">
              <h3>Бренд</h3>
              ${brands
                .map(
                  (brand) => `
                <label class="check">
                  <input type="checkbox" name="brand" value="${escapeHtml(brand)}" ${state.brand.includes(brand) ? "checked" : ""}>
                  <span>${escapeHtml(brand)}</span>
                  <span class="check__count">${brandCount(brand)}</span>
                </label>`
                )
                .join("")}
            </div>

            <div class="filters__group">
              <h3>Наличие</h3>
              <label class="check">
                <input type="checkbox" name="stock" ${state.stock ? "checked" : ""}>
                <span>Только в наличии</span>
              </label>
            </div>

            <div class="filters__group">
              <h3>Цена, ₽</h3>
              <form class="filters__price" data-price-form>
                <input type="text" inputmode="numeric" name="min" placeholder="от" value="${escapeHtml(state.min)}" aria-label="Минимальная цена">
                <input type="text" inputmode="numeric" name="max" placeholder="до" value="${escapeHtml(state.max)}" aria-label="Максимальная цена">
                <button type="submit">Применить</button>
              </form>
            </div>
          </aside>

          <section aria-label="Результаты">
            <div class="results__toolbar">
              <button class="filters-toggle" type="button" data-toggle-filters aria-expanded="false">Фильтры</button>
              <p class="results__count" data-count></p>
              <label class="results__sort">
                Сортировка
                <select data-sort aria-label="Сортировка товаров">
                  <option value="relevance" ${state.sort === "relevance" ? "selected" : ""}>По релевантности</option>
                  <option value="price-asc" ${state.sort === "price-asc" ? "selected" : ""}>Сначала дешёвые</option>
                  <option value="price-desc" ${state.sort === "price-desc" ? "selected" : ""}>Сначала дорогие</option>
                  <option value="stock" ${state.sort === "stock" ? "selected" : ""}>По наличию</option>
                </select>
              </label>
            </div>
            <div class="results__query" data-query-chips hidden></div>
            <div class="results__grid" data-grid></div>
          </section>
        </div>
      </div>`;

    const filters = app.querySelector("[data-filters]");
    const grid = app.querySelector("[data-grid]");
    const count = app.querySelector("[data-count]");
    const title = app.querySelector("[data-page-title]");
    const subtitle = app.querySelector("[data-page-sub]");
    const chips = app.querySelector("[data-query-chips]");
    const sortSelect = app.querySelector("[data-sort]");
    const filtersToggle = app.querySelector("[data-toggle-filters]");

    function apply() {
      const results = filterProducts(state);
      title.textContent = pageTitle(state, isSearch);
      subtitle.textContent = pageSubtitle(state, isSearch);
      count.innerHTML = `<b>${results.length}</b> ${plural(results.length, ["товар", "товара", "товаров"])}`;
      grid.innerHTML = results.length
        ? results.map(productCard).join("")
        : `<div class="empty">
            <h2>Ничего не нашли</h2>
            <p>Попробуйте изменить запрос или открыть весь каталог — в нём ${PRODUCTS.length} позиций.</p>
            <div class="empty__actions">
              <a class="btn btn--primary" href="#/catalog">Открыть весь каталог</a>
              ${CONTACTS.phoneHref ? `<a class="btn btn--outline" href="tel:${escapeHtml(CONTACTS.phoneHref)}">Позвонить</a>` : ""}
            </div>
          </div>`;
      const active = [
        ...(state.q ? [["q", state.q]] : []),
        ...(state.model ? [["model", state.model]] : []),
        ...state.cat.map(id => ["cat", categoryName(id), id]),
        ...state.brand.map(brand => ["brand", brand, brand]),
        ...(state.stock ? [["stock", "В наличии"]] : []),
        ...(state.min ? [["min", "От " + formatPrice(state.min)]] : []),
        ...(state.max ? [["max", "До " + formatPrice(state.max)]] : [])
      ];
      chips.hidden = !active.length;
      chips.innerHTML = active.map(([key, label, value]) => `<button type="button" data-clear-filter="${key}" data-value="${escapeHtml(value || "")}">${escapeHtml(label)} ×</button>`).join("");
      syncShoppingControls();
      history.replaceState(null, "", "#" + buildUrl(base, state));
      setActiveCat(state.cat.length === 1 ? state.cat[0] : "all");
      document.title = `${pageTitle(state, isSearch)} — PartStack`;
    }

    function syncControls() {
      filters.querySelectorAll('input[name="cat"]').forEach((input) => {
        input.checked = state.cat.includes(input.value);
      });
      filters.querySelectorAll('input[name="brand"]').forEach((input) => {
        input.checked = state.brand.includes(input.value);
      });
      const stock = filters.querySelector('input[name="stock"]');
      if (stock) stock.checked = state.stock;
      const min = filters.querySelector('input[name="min"]');
      const max = filters.querySelector('input[name="max"]');
      if (min) min.value = state.min;
      if (max) max.value = state.max;
      sortSelect.value = state.sort;
    }

    filters.addEventListener("change", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLInputElement)) return;
      if (target.name === "cat") {
        state.cat = Array.from(filters.querySelectorAll('input[name="cat"]:checked')).map(
          (input) => input.value
        );
      } else if (target.name === "brand") {
        state.brand = Array.from(filters.querySelectorAll('input[name="brand"]:checked')).map(
          (input) => input.value
        );
      } else if (target.name === "stock") {
        state.stock = target.checked;
      }
      apply();
    });

    filters.querySelector("[data-price-form]").addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const min = String(form.elements.min.value || "").replace(/\D/g, "");
      const max = String(form.elements.max.value || "").replace(/\D/g, "");
      state.min = min;
      state.max = max;
      if (min && max && Number(min) > Number(max)) {
        state.min = max; state.max = min;
      }
      syncControls();
      apply();
    });

    filters.querySelector("[data-reset-filters]").addEventListener("click", () => {
      state.model = "";
      state.cat = [];
      state.brand = [];
      state.stock = false;
      state.min = "";
      state.max = "";
      state.sort = "relevance";
      syncControls();
      apply();
    });

    sortSelect.addEventListener("change", () => {
      state.sort = sortSelect.value;
      apply();
    });

    filtersToggle.addEventListener("click", () => {
      const isOpen = filters.classList.toggle("is-open");
      filtersToggle.setAttribute("aria-expanded", String(isOpen));
      filtersToggle.textContent = isOpen ? "Скрыть фильтры" : "Фильтры";
    });

    app.querySelector("[data-query-chips]").addEventListener("click", (event) => {
      const button = event.target.closest("[data-clear-filter]");
      if (!button) return;
      const key = button.dataset.clearFilter;
      if (key === "cat" || key === "brand") state[key] = state[key].filter(value => value !== button.dataset.value);
      else state[key] = key === "stock" ? false : "";
      syncControls();
      apply();
      syncHeaderSearch(getRoute());
    });

    apply();
  }

  /* ---------- Карточка товара ---------- */

  const PART_DESCRIPTIONS = {
    batteries: "Аккумулятор стоит заменить, если телефон стал быстро разряжаться или выключаться под нагрузкой. Перед покупкой сверьте маркировку батареи и модель телефона.",
    flex: "Шлейф соединяет узлы телефона с платой. Его меняют при повреждении дорожек или контактов. Сверьте назначение шлейфа, форму и расположение разъёмов.",
    cameras: "Модуль камеры меняют при неисправности самого модуля, например если пропал фокус. Сверьте модель телефона и тип камеры: фронтальная, основная или дополнительная.",
    glass: "Защитное стекло или плёнка помогают уберечь поверхность экрана от царапин. Подбирайте покрытие под точную модель телефона и форму экрана.",
    covers: "Деталь для восстановления корпуса после трещин, сколов или деформации. Проверьте цвет, расположение вырезов и комплектность: клей, стекло камеры и кнопки могут продаваться отдельно.",
    charging: "Разъём меняют при механическом повреждении порта или плохом контакте кабеля. Сверьте тип порта и исполнение: отдельный разъём под пайку или деталь со шлейфом.",
    "lower-boards": "Нижняя плата в сборе используется для замены нижнего узла телефона. В зависимости от модели на ней могут находиться порт зарядки, микрофон и контакты антенны. Сверьте маркировку и ревизию платы.",
    boards: "Основная плата управляет работой телефона. Перед заменой сверьте модель, региональную версию, объём памяти и комплектность.",
    "board-components": "Компонент для ремонта платы на уровне отдельных элементов. Для подбора сверьте маркировку, корпус и назначение детали. Монтаж может требовать пайки.",
    speakers: "Динамик используют для восстановления звука при неисправности модуля. При подборе проверьте модель телефона и тип динамика: разговорный или полифонический.",
    tools: "Инструмент для ремонта электроники. Перед работой проверьте, подходит ли он для нужной операции и размеров детали.",
  };

  /** Выбирает описание по указанному типу матрицы и варианту товара. */
  function getDisplayDescription(product) {
    const variant = normalize([product.name, product.subtitle, product.specs?.["Тип матрицы"]].filter(Boolean).join(" "));
    if (/\b(?:original|service pack)\b|(?:^| )оригинал(?:ьный)?(?: |$)/.test(variant) &&
        !/(?:^| )(?:не|под) оригинал|неоригинал|\b(?:non|not) original\b/.test(variant)) {
      return "Оригинальный дисплей — заводской модуль для указанной модели. Его выбирают, чтобы сохранить штатные характеристики экрана и посадку в корпусе. Перед покупкой уточните комплектацию и нужна ли настройка после установки.";
    }
    if (/\bin ?cell\b/.test(variant)) {
      return "In-Cell — LCD-модуль с сенсором, встроенным в матрицу. Это бюджетный вариант замены. По сравнению со штатным OLED такой модуль может быть толще и уступать по контрасту. Для переноса микросхемы подойдёт версия, у которой прямо заявлена поддержка IC Transfer.";
    }
    if (/\b(?:amoled|oled)\b/.test(variant)) {
      return "OLED даёт глубокий чёрный и высокий контраст. Цветопередача может быть лучше, чем у бюджетной LCD-замены, но зависит от конкретной матрицы. У совместимого OLED рамки могут быть шире, чем у заводского экрана.";
    }
    if (/\b(?:lcd|ips|tft)\b/.test(variant)) {
      return "LCD — дисплей с подсветкой. Модуль подходит для замены повреждённого экрана указанной модели. Перед установкой проверьте яркость, изображение и отклик сенсора.";
    }
    return "Дисплейный модуль для замены повреждённого экрана. Сверьте точную модель телефона, тип матрицы и комплектацию: с рамкой или без.";
  }

  /** Берёт текст из админки, а для пустых полей подставляет справку о детали. */
  function getProductDescription(product) {
    const custom = product.description?.trim();
    if (custom) return custom;
    if (product.category === "displays") return getDisplayDescription(product);
    return PART_DESCRIPTIONS[product.category] ||
      "Перед покупкой сверьте артикул, совместимость и комплектацию с вашей деталью.";
  }

  function renderProduct(product) {
    document.title = `${product.name} — PartStack`;
    setActiveCat(product.category);
    const category = categoryById.get(product.category);
    const isOut = product.stock <= 0;
    const related = PRODUCTS.filter(
      (item) => item.category === product.category && item.id !== product.id
    ).slice(0, 4);
    const discount = product.oldPrice
      ? Math.round((1 - product.price / product.oldPrice) * 100)
      : 0;
    const specs = Object.assign({}, product.specs, {
      Гарантия: product.warranty,
      Наличие: isOut ? "Под заказ" : `${product.stock} шт. в Рязани`,
    });

    app.innerHTML = `
      <div class="product${isOut ? " product--out" : ""}">
        <div class="container">
          <nav class="crumbs" aria-label="Хлебные крошки">
            <a href="#/">Главная</a><span>/</span>
            <a href="#/catalog">Каталог</a><span>/</span>
            <a href="#/search?cat=${product.category}">${escapeHtml(category.name)}</a><span>/</span>
            <span>${escapeHtml(product.name)}</span>
          </nav>

          <div class="product__grid">
            <div class="product__left">
              <div class="product__media">
                <img data-product-image src="${productImage(product)}" alt="${escapeHtml(product.name)}" width="330" height="330">
                ${(product.images || []).length > 1 ? `<div class="photo-gallery">${product.images.map((url, index) => `<button type="button" data-photo="${escapeHtml(url)}" aria-label="Фото ${index + 1}"><img src="${escapeHtml(url)}" width="60" height="60" alt=""></button>`).join("")}</div>` : ""}
                <div class="product__badges">
                  ${product.badge ? `<span class="badge badge--hit">${escapeHtml(product.badge)}</span>` : ""}
                  ${discount >= 5 ? `<span class="badge badge--sale">−${discount}%</span>` : ""}
                  ${isOut ? '<span class="badge badge--out">Нет в наличии</span>' : ""}
                </div>
                <span class="product__media-meta">${product.images?.length ? "Фото товара" : "Схема · " + escapeHtml(category.name)}</span>
              </div>

              <ul class="product__assurance">
                <li>
                  ${ICONS.check}
                  <div><b>Гарантия ${escapeHtml(product.warranty)}</b><span><a href="#/how-to-order">Условия покупки и гарантии</a></span></div>
                </li>
                <li>
                  ${ICONS.pin}
                  <div><b>Самовывоз в Рязани</b><span>Проверьте деталь на месте</span></div>
                </li>
                <li>
                  ${ICONS.copy}
                  <div><b>Оплата при получении</b><span>Без предоплаты</span></div>
                </li>
              </ul>
            </div>

            <div class="product__info">
              <p class="eyebrow">${escapeHtml(category.name)}</p>
              <h1>${escapeHtml(product.name)}</h1>
              <p class="product__sub">${escapeHtml(product.subtitle)}</p>
              <span class="product__part">Артикул <b>${escapeHtml(product.part)}</b></span>

              <div class="product__buy">
                <div class="product__price">
                  ${product.oldPrice ? `<s>${formatPrice(product.oldPrice)}</s>` : ""}
                  <b>${formatPrice(product.price)}</b>
                </div>
                <p class="product__stock">${isOut ? "Нет в наличии — уточните срок" : `В наличии · ${product.stock} шт.`}</p>
                ${renderFavoriteButton(product)}
              <div class="product__controls">
                  <div class="qty">
                    <button type="button" data-qty-minus aria-label="Уменьшить количество" ${isOut ? "disabled" : ""}>−</button>
                    <output data-qty-value>1</output>
                    <button type="button" data-qty-plus aria-label="Увеличить количество" ${isOut ? "disabled" : ""}>+</button>
                  </div>
                  <button class="btn btn--primary" type="button" data-product-add ${isOut ? "disabled" : ""}>
                    ${isOut ? "Нет в наличии" : "В корзину"}
                  </button>
                </div>
              </div>

              <div class="pickup-note">
                ${ICONS.pin}
                <div>
                  <b>Самовывоз после подтверждения</b>
                  ${escapeHtml(CONTACTS.addressFull)} · ${escapeHtml(CONTACTS.hours)}
                </div>
              </div>

              <section class="specs product-description">
                <h2>О детали</h2>
                <p>${escapeHtml(getProductDescription(product))}</p>
              </section>

              <div class="specs">
                <h2>Характеристики</h2>
                <dl>
                  ${Object.entries(specs)
                    .map(
                      ([label, value]) =>
                        `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`
                    )
                    .join("")}
                </dl>
              </div>

              <div class="specs">
                <h2>Совместимость</h2>
                <div class="compat">
                  ${product.compat.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
                </div>
              </div>
            </div>
          </div>

          ${
            related.length
              ? `<section class="related">
                  <h2>Ещё из категории «${escapeHtml(category.name)}»</h2>
                  <div class="product-grid">${related.map(productCard).join("")}</div>
                </section>`
              : ""
          }
        </div>
      </div>`;

    app.querySelectorAll("[data-photo]").forEach(button => button.addEventListener("click", () => { app.querySelector("[data-product-image]").src = button.dataset.photo; }));
    let qty = 1;
    const value = app.querySelector("[data-qty-value]");
    const plus = app.querySelector("[data-qty-plus]");
    const minus = app.querySelector("[data-qty-minus]");
    const add = app.querySelector("[data-product-add]");

    function refreshQty() {
      value.textContent = String(qty);
      minus.disabled = isOut || qty <= 1;
      plus.disabled = isOut || qty >= product.stock;
    }

    plus.addEventListener("click", () => {
      if (qty < product.stock) {
        qty += 1;
        refreshQty();
      }
    });

    minus.addEventListener("click", () => {
      if (qty > 1) {
        qty -= 1;
        refreshQty();
      }
    });

    add.addEventListener("click", () => {
      addToCart(product.id, qty);
    });

    refreshQty();
  }

  /* ---------- Корзина ---------- */

  function cartItemHtml(item) {
    const product = item.product;
    return `
      <article class="cart-item">
        <a class="cart-item__media" href="#/product/${product.slug}" aria-label="${escapeHtml(product.name)}">
          <img src="${productImage(product)}" alt="" width="92" height="92" loading="lazy">
        </a>
        <div>
          <h2 class="cart-item__title"><a href="#/product/${product.slug}">${escapeHtml(product.name)}</a></h2>
          <p class="cart-item__meta">${escapeHtml(product.part)} · <span class="stock">${product.stock} шт. на складе</span></p>
        </div>
        <div class="qty">
          <button type="button" data-cart-minus="${product.id}" aria-label="Уменьшить количество">−</button>
          <output>${item.qty}</output>
          <button type="button" data-cart-plus="${product.id}" aria-label="Увеличить количество">+</button>
        </div>
        <div class="cart-item__right">
          <span class="cart-item__price">${formatPrice(product.price * item.qty)}</span>
          <button class="cart-item__remove" type="button" data-cart-remove="${product.id}">Удалить</button>
        </div>
      </article>`;
  }

  function summaryHtml(items) {
    const count = items.reduce((sum, item) => sum + item.qty, 0);
    const total = items.reduce((sum, item) => sum + item.product.price * item.qty, 0);
    return `
      <aside class="summary">
        <h2>Ваш заказ</h2>
        <div class="summary__pickup">
          ${ICONS.pin}
          <div><b>Самовывоз</b><br>${escapeHtml(CONTACTS.addressFull)}</div>
        </div>
        <div class="summary__row"><span>Товары (${count})</span><b>${formatPrice(total)}</b></div>
        <div class="summary__row"><span>Доставка</span><b>Самовывоз</b></div>
        <div class="summary__total"><span>Итого</span><b>${formatPrice(total)}</b></div>
        <a class="btn btn--primary btn--wide" href="#/checkout">Оформить заказ</a>
        <p class="summary__note">Отправьте состав корзины в Telegram. Сотрудник подтвердит наличие, итоговую цену и время самовывоза. Оплата при получении — наличными или картой.</p>
        <a class="summary__guide" href="#/how-to-order">Как заказать и оплатить</a>
      </aside>`;
  }

  function renderCart() {
    document.title = "Корзина — PartStack";
    setActiveCat(null);
    const items = cartItems();
    if (!items.length) {
      app.innerHTML = `
        <div class="cart-page">
          <div class="container">
            <nav class="crumbs" aria-label="Хлебные крошки"><a href="#/">Главная</a><span>/</span><span>Корзина</span></nav>
            <h1>Корзина</h1>
            <div class="empty">
              <h2>Пока пусто</h2>
              <p>Найдите деталь по модели или артикулу — добавьте её в корзину, чтобы оформить самовывоз в Рязани.</p>
              <div class="empty__actions">
                <a class="btn btn--primary" href="#/catalog">Открыть каталог</a>
                <a class="btn btn--outline" href="#/">На главную</a>
              </div>
            </div>
          </div>
        </div>`;
      return;
    }

    app.innerHTML = `
      <div class="cart-page">
        <div class="container">
          <nav class="crumbs" aria-label="Хлебные крошки"><a href="#/">Главная</a><span>/</span><span>Корзина</span></nav>
          <h1>Корзина</h1>
          <div class="cart-layout">
            <div class="cart-list">${items.map(cartItemHtml).join("")}</div>
            ${summaryHtml(items)}
          </div>
        </div>
      </div>`;

    app.querySelectorAll("[data-cart-plus]").forEach((button) => {
      button.addEventListener("click", () => {
        const id = Number(button.dataset.cartPlus);
        const item = cart.find((entry) => entry.id === id);
        const product = productById.get(id);
        if (!item || !product) return;
        if (item.qty >= product.stock) {
          showToast(`В наличии только ${product.stock} шт.`);
          return;
        }
        setCartQty(id, item.qty + 1);
        rerenderCart();
      });
    });

    app.querySelectorAll("[data-cart-minus]").forEach((button) => {
      button.addEventListener("click", () => {
        const id = Number(button.dataset.cartMinus);
        const item = cart.find((entry) => entry.id === id);
        if (!item) return;
        setCartQty(id, item.qty - 1);
        rerenderCart();
      });
    });

    app.querySelectorAll("[data-cart-remove]").forEach((button) => {
      button.addEventListener("click", () => {
        removeFromCart(Number(button.dataset.cartRemove));
        rerenderCart();
      });
    });
  }

  function rerenderCart() {
    const y = window.scrollY;
    renderCart();
    window.scrollTo(0, y);
  }

  /* ---------- Оформление ---------- */

  /** Возвращает только HTTPS-ссылку на настроенное сообщество магазина. */
  function getSocialUrl(key) {
    try {
      const url = new URL(SOCIAL_LINKS[key]);
      return url.protocol === "https:" ? url.href : "";
    } catch (error) { return ""; }
  }

  /** Собирает текст обращения только из товарных данных корзины. */
  function buildCartMessage(items) {
    if (!items.length) return "";
    const lines = items.map(({product, qty}, index) =>
      `${index + 1}. ${product.name} — ${product.subtitle}\nАртикул: ${product.part}\n${qty} шт. × ${formatPrice(product.price)} = ${formatPrice(product.price * qty)}`);
    const total = items.reduce((sum, {product, qty}) => sum + product.price * qty, 0);
    return ["Здравствуйте! Хочу оформить заказ:", "", ...lines, "", `Итого: ${formatPrice(total)}`, "Подтвердите, пожалуйста, наличие и актуальную стоимость."].join("\n");
  }

  /** Добавляет черновик к ссылке чата; длинный список оставляет для копирования. */
  function buildTelegramLink(message) {
    const base = getSocialUrl("telegram");
    if (!base || !message) return {url: base, manual: false};
    const url = new URL(base);
    url.searchParams.set("text", message);
    const manual = message.length > 4000 || url.href.length > 8000;
    return {url: manual ? base : url.href, manual};
  }

  /** Копирует состав корзины или выделяет его для ручного копирования. */
  async function copyCartMessage(message) {
    try {
      await navigator.clipboard.writeText(message);
      showToast("Состав заказа скопирован — вставьте его в переписку с магазином");
    } catch (error) {
      const preview = app.querySelector("[data-order-preview]");
      preview.closest("details").open = true;
      const range = document.createRange();
      range.selectNodeContents(preview);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      showToast("Не удалось скопировать автоматически. Текст выделен — скопируйте его вручную.");
    }
  }

  /** Показывает порядок покупки и актуальные контакты магазина. */
  function renderOrderGuide() {
    document.title = "Как заказать — PartStack";
    setActiveCat(null);
    const telegram = getSocialUrl("telegram");
    app.innerHTML = `
      <section class="checkout-page"><div class="container order-guide">
        <nav class="crumbs" aria-label="Хлебные крошки"><a href="#/">Главная</a><span>/</span><span>Как заказать</span></nav>
        <h1>Как заказать</h1>
        <div class="order-guide__layout">
          <div class="order-guide__body">
            <section>
              <h2>Подтверждение заказа</h2>
              <ol>
                <li>Выберите запчасти, добавьте их в корзину и нажмите «Оформить заказ».</li>
                <li>Откройте Telegram и отправьте подготовленное сообщение с товарами.</li>
                <li>Дождитесь ответа сотрудника. Он подтвердит наличие и итоговую цену, уточнит совместимость при необходимости и согласует адрес и время самовывоза.</li>
              </ol>
            </section>
            <section>
              <h2>Оплата</h2>
              <p>Оплатите заказ при получении наличными или картой. Удобный способ оплаты можно согласовать в переписке.</p>
            </section>
            <section>
              <h2>Гарантия и возврат</h2>
              <p>Гарантийный срок зависит от запчасти. Если он указан, его можно посмотреть в карточке товара. Уточнить условия для выбранной детали можно у сотрудника перед покупкой.</p>
              <p>Если обнаружили недостаток или хотите оформить возврат, свяжитесь с магазином. Укажите артикул и дату покупки, опишите проблему и приложите фото, если это поможет её показать. Сотрудник подскажет, как передать товар на проверку и оформить обращение.</p>
            </section>
          </div>
          <aside class="summary order-guide__pickup">
            <h2>Самовывоз</h2>
            <p><strong>${escapeHtml(CONTACTS.addressFull)}</strong></p>
            <p>${escapeHtml(CONTACTS.hours)}</p>
            <p>Перед поездкой дождитесь подтверждения адреса и времени в переписке.</p>
            ${CONTACTS.phoneHref ? `<p><a href="tel:${escapeHtml(CONTACTS.phoneHref)}">${escapeHtml(CONTACTS.phone)}</a></p>` : ""}
            ${telegram ? `<a class="btn btn--primary" href="${escapeHtml(telegram)}" target="_blank" rel="noopener noreferrer">Написать в Telegram</a>` : ""}
          </aside>
        </div>
      </div></section>`;
  }

  /** Показывает выбор соцсети без сбора контактов и создания заказа. */
  function renderCheckout() {
    const message = buildCartMessage(cartItems());
    const telegram = buildTelegramLink(message);
    const telegramLabel = telegram.url ? "@" + new URL(telegram.url).pathname.replace(/^\/|\/$/g, "") : "";
    document.title = "Оформление через соцсети — PartStack";
    setActiveCat(null);
    app.innerHTML = `
      <section class="checkout-page"><div class="container">
        <nav class="crumbs" aria-label="Хлебные крошки"><a href="#/">Главная</a><span>/</span><a href="#/cart">Корзина</a><span>/</span><span>Оформление</span></nav>
        <h1>Оформление заказа</h1>
        <div class="social-checkout">
          <p class="eyebrow">Продолжим в соцсетях</p>
          <h2>Куда вам удобнее написать?</h2>
          <p>Отправьте сообщение с товарами. Сотрудник подтвердит наличие и цену, согласует самовывоз и способ оплаты.</p>
          <a class="summary__guide" href="#/how-to-order">Оплата, самовывоз и гарантия</a>
          <div class="social-checkout__links">
            ${[["telegram", "Telegram"], ["vk", "ВКонтакте"]].map(([key, label]) => {
              const url = key === "telegram" ? telegram.url : getSocialUrl(key);
              const body = `${ICONS[key]}<span><b>${label}</b><small>${url ? (key === "telegram" ? escapeHtml(telegramLabel) : "Написать для оформления") : "Скоро появится"}</small></span><span aria-hidden="true">${url ? "↗" : "Скоро"}</span>`;
              return url ? `<a class="social-contact" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${body}</a>` : `<button class="social-contact" type="button" disabled>${body}</button>`;
            }).join("")}
          </div>
          ${message ? `<div class="checkout-message"><p>${!telegram.url ? "Скопируйте список товаров и вставьте его в переписку с магазином." : telegram.manual ? "Большой заказ: скопируйте список ниже и вставьте его в чат Telegram." : "В Telegram откроется сообщение с товарами из корзины. Проверьте его и нажмите «Отправить». Если текст не подставился, скопируйте его ниже."}</p><button class="btn btn--outline" type="button" data-copy-cart>Скопировать состав заказа</button><details><summary>Посмотреть текст сообщения</summary><pre data-order-preview>${escapeHtml(message)}</pre></details></div>` : '<p class="social-checkout__note-empty">Корзина пуста. Можно написать нам с вопросом или сначала выбрать товары в каталоге.</p>'}
          <p class="social-checkout__note">Контакты для оформления пока готовим. Как только сообщества появятся, здесь будут ссылки для связи.</p>
          <a class="model-entry" href="#/cart">← Вернуться в корзину</a>
        </div>
      </div></section>`;
    app.querySelector("[data-copy-cart]")?.addEventListener("click", () => copyCartMessage(message));
    app.querySelector(".social-checkout__note").hidden = Boolean(getSocialUrl("vk") || getSocialUrl("telegram"));
  }

  /** Удаляет контакты и историю, сохранённые прежней формой оформления. */
  function clearLegacyCustomerData() {
    try {
      localStorage.removeItem("z62_customer_v1");
      localStorage.removeItem("z62_orders_v1");
    } catch (error) {
      console.warn("Не удалось удалить данные прежней формы из хранилища браузера.");
    }
  }

  /* ---------- 404 ---------- */

  function renderNotFound(message) {
    document.title = `${message} — PartStack`;
    setActiveCat(null);
    app.innerHTML = `
      <div class="cart-page">
        <div class="container">
          <nav class="crumbs" aria-label="Хлебные крошки"><a href="#/">Главная</a><span>/</span><span>${escapeHtml(message)}</span></nav>
          <div class="empty" style="margin-top: 24px;">
            <h2>${escapeHtml(message)}</h2>
            <p>Проверьте адрес или вернитесь в каталог — там все запчасти с наличием в Рязани.</p>
            <div class="empty__actions">
              <a class="btn btn--primary" href="#/catalog">Открыть каталог</a>
              <a class="btn btn--outline" href="#/">На главную</a>
            </div>
          </div>
        </div>
      </div>`;
  }

  /* ---------- Глобальные обработчики ---------- */

  document.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-search-form]");
    if (!form) return;
    event.preventDefault();
    const query = String(form.querySelector("input[name='q']").value || "").trim();
    navigate(query ? "/search?q=" + encodeURIComponent(query) : "/catalog");
  });

  document.addEventListener("click", (event) => {
    const addButton = event.target.closest("[data-add]");
    if (addButton) {
      event.preventDefault();
      addToCart(Number(addButton.dataset.add), 1);
      return;
    }

    const social = event.target.closest("[data-social]");
    if (social && !SOCIAL_LINKS[social.dataset.social]) {
      event.preventDefault();
      showToast("Сообщество магазина скоро появится.");
    }
  });

  /** Читает избранное, отбрасывая неизвестные товары. */
  function readFavorites() {
    try {
      const ids = JSON.parse(localStorage.getItem("z62_favorites") || "[]");
      return Array.isArray(ids) ? [...new Set(ids.filter(id => productById.has(id)))] : [];
    } catch (error) { return []; }
  }

  /** Создаёт переключатель избранного для товара. */
  function renderFavoriteButton(product) {
    return `<div class="save-actions">
      <button type="button" data-favorite="${product.id}" aria-pressed="${favorites.includes(product.id)}">
        <svg class="favorite-heart" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.2 4.4 13a4.7 4.7 0 0 1 6.6-6.7l1 1 1-1a4.7 4.7 0 0 1 6.6 6.7Z"/></svg>
        Избранное
      </button>
    </div>`;
  }

  /** Обновляет состояние кнопок без перерисовки страницы и потери фокуса. */
  function syncShoppingControls() {
    document.querySelectorAll("[data-add]").forEach(button => {
      const product = productById.get(Number(button.dataset.add));
      const item = cart.find(entry => entry.id === product.id);
      button.textContent = !product.stock ? "Нет в наличии" : item ? `В корзине: ${item.qty} · +` : "В корзину";
      button.classList.toggle("is-added", Boolean(item));
    });
    document.querySelectorAll("[data-favorite]").forEach(button => {
      const selected = favorites.includes(Number(button.dataset.favorite));
      button.setAttribute("aria-pressed", String(selected));
    });
    document.querySelectorAll("[data-favorite-count]").forEach(node => {
      node.textContent = favorites.length;
    });
  }

  /** Выводит пошаговый подбор по бренду и точной совместимости. */
  function renderModels() {
    document.title = "Подбор по модели — PartStack";
    setActiveCat(null);
    const brands = [...new Set(PRODUCTS.filter(product => product.category !== "tools").map(product => product.brand))];
    app.innerHTML = `<section class="section"><div class="container"><nav class="crumbs"><a href="#/catalog">Каталог</a><span>/</span><span>Подбор по модели</span></nav><h1>Какая у вас модель?</h1><p class="pagehead__sub">Выберите производителя, затем модель. Покажем только совместимые детали.</p><div class="model-brands">${brands.map(brand => `<button class="btn btn--outline" data-model-brand="${escapeHtml(brand)}" aria-pressed="false">${escapeHtml(brand)}</button>`).join("")}</div><label class="model-search">Найти модель<input type="search" data-model-search placeholder="Например, iPhone 11" aria-label="Найти модель"></label><div class="model-grid" data-model-grid></div></div></section>`;
    let selectedBrand = "";
    const input = app.querySelector("[data-model-search]");
    /** Перестраивает список моделей по выбранному бренду и тексту. */
    function updateModels() {
      const products = PRODUCTS.filter(product => product.category !== "tools" && (!selectedBrand || product.brand === selectedBrand));
      const models = [...new Set(products.flatMap(product => product.compat))].filter(model => normalize(model).includes(normalize(input.value))).sort((left, right) => left.localeCompare(right, "ru", {numeric: true}));
      app.querySelector("[data-model-grid]").innerHTML = models.length ? models.map(model => `<a class="model-tile" href="#/catalog?model=${encodeURIComponent(model)}"><b>${escapeHtml(model)}</b><span>${PRODUCTS.filter(product => product.compat.includes(model)).length} позиций ${ICONS.arrow}</span></a>`).join("") : '<p>Модель не найдена. Измените запрос или выберите другой бренд.</p>';
    }
    app.querySelectorAll("[data-model-brand]").forEach(button => button.addEventListener("click", () => {
      selectedBrand = selectedBrand === button.dataset.modelBrand ? "" : button.dataset.modelBrand;
      app.querySelectorAll("[data-model-brand]").forEach(node => node.setAttribute("aria-pressed", String(node.dataset.modelBrand === selectedBrand)));
      updateModels();
    }));
    input.addEventListener("input", updateModels);
    updateModels();
  }

  /** Показывает товары, сохранённые в избранном. */
  function renderFavorites() {
    const title = "Избранное";
    document.title = title + " — PartStack";
    setActiveCat(null);
    const products = favorites.map(id => productById.get(id));
    const content = products.length
      ? `<div class="product-grid">${products.map(productCard).join("")}</div>`
      : '<div class="empty"><h2>Сохраните нужные детали</h2><p>Нажмите «Избранное» на карточке товара. Подборка останется после перезагрузки.</p><a class="btn btn--primary" href="#/catalog">Открыть каталог</a></div>';
    app.innerHTML = `<section class="section"><div class="container"><nav class="crumbs"><a href="#/">Главная</a><span>/</span><span>${title}</span></nav><div class="section__head"><h1>${title}</h1><a href="#/catalog">Продолжить покупки →</a></div>${content}</div></section>`;
  }

  /** Подключает подсказки поиска с клавиатурной навигацией и закрытием. */
  function initializeSearch() {
    const form = document.querySelector("[data-search-form]");
    const input = form.querySelector("input");
    const panel = document.createElement("div");
    panel.className = "search-suggestions";
    panel.dataset.suggestions = "";
    panel.id = "search-suggestions";
    panel.hidden = true;
    form.append(panel);
    input.setAttribute("aria-controls", panel.id);
    /** Обновляет подсказки по тем же правилам, что основной поиск. */
    function updateSuggestions() {
      const query = input.value.trim();
      const matches = query ? filterProducts(filtersFromQuery(new URLSearchParams({q:query}))).slice(0,5) : [];
      panel.hidden = !query;
      input.setAttribute("aria-expanded", String(Boolean(query)));
      panel.innerHTML = matches.map(product => `<a href="#/product/${product.slug}"><img src="${productImage(product)}" width="36" height="36" alt=""><span>${escapeHtml(product.name)}<small>${escapeHtml(product.subtitle)} · ${escapeHtml(product.part)}</small></span><b>${formatPrice(product.price)}</b></a>`).join("") + `<a class="search-all" href="#/search?q=${encodeURIComponent(query)}">${matches.length ? "Все результаты" : "Нет совпадений — изменить поиск"} ${ICONS.arrow}</a>`;
    }
    input.addEventListener("input", updateSuggestions);
    input.addEventListener("focus", updateSuggestions);
    form.addEventListener("keydown", event => {
      if (event.key === "Escape") { panel.hidden = true; input.setAttribute("aria-expanded", "false"); input.focus(); panel.hidden = true; }
      if ((event.key === "ArrowDown" || event.key === "ArrowUp") && !panel.hidden) {
        event.preventDefault();
        const links = [...panel.querySelectorAll("a")];
        const index = links.indexOf(document.activeElement);
        links[(index + (event.key === "ArrowDown" ? 1 : -1) + links.length) % links.length].focus();
      }
    });
    document.addEventListener("click", event => { if (!form.contains(event.target)) { panel.hidden = true; input.setAttribute("aria-expanded", "false"); } });
    form.addEventListener("focusout", event => { if (!form.contains(event.relatedTarget)) panel.hidden = true; });
  }

  document.addEventListener("click", event => {
    const button = event.target.closest("[data-favorite]");
    if (!button) return;
    const id = Number(button.dataset.favorite);
    if (!productById.has(id)) return;
    const index = favorites.indexOf(id);
    if (index < 0) favorites.push(id);
    else favorites.splice(index, 1);
    try { localStorage.setItem("z62_favorites", JSON.stringify(favorites)); } catch (error) { showToast("Подборка доступна до закрытия страницы: сохранение недоступно."); }
    if (getRoute().path === "/favorites") renderFavorites();
    syncShoppingControls();
    const heart = button.querySelector(".favorite-heart");
    heart?.getAnimations?.().forEach(animation => animation.cancel());
    if (index < 0 && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      heart?.animate?.([
        { transform: "scale(0.88)" },
        { transform: "scale(1.32)", offset: 0.45 },
        { transform: "scale(1)" },
      ], { duration: 320, easing: "ease-out" });
    }
  });

  /* ---------- Запуск ---------- */

  document.querySelectorAll("[data-shop-address]").forEach(node => { node.textContent = CONTACTS.addressFull; });
  document.querySelectorAll("[data-shop-hours]").forEach(node => { node.textContent = CONTACTS.hours; });
  document.querySelectorAll("[data-shop-phone]").forEach(link => {
    if (!CONTACTS.phoneHref) return;
    link.href = "tel:" + CONTACTS.phoneHref;
    link.textContent = CONTACTS.phone;
    link.hidden = false;
  });
  document.querySelectorAll("[data-social]").forEach(link => {
    const url = getSocialUrl(link.dataset.social);
    if (url) { link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; }
  });
  clearLegacyCustomerData();
  initializeSearch();

  renderCatnav();
  renderFooterCategories();
  updateCartBadge();
  window.addEventListener("hashchange", render);
  render();
})();
