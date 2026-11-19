/** Загружает ограниченную витрину с тайм-аутом и повторной попыткой. */
(function () {
  "use strict";
  const app = document.getElementById('app');
  let loading = false;

  /** Получает свежие данные и отменяет зависшие или устаревшие запросы. */
  async function fetchCatalog(parameters = {}, signal) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener('abort', abort, {once: true});
    const timeout = setTimeout(abort, 10000);
    try {
      const response = await fetch('/api/catalog/?' + new URLSearchParams(parameters), {cache: 'no-store', signal: controller.signal});
      if (!response.ok) throw new Error('Каталог недоступен');
      const data = await response.json();
      if (!Array.isArray(data.PRODUCTS) && !Array.isArray(data.models)) throw new Error('Некорректный ответ каталога');
      return data;
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener('abort', abort);
    }
  }
  window.shopFetchCatalog = fetchCatalog;

  /** Загружает сохранённые позиции порциями, не обрезая большую корзину. */
  async function fetchProductsByIds(ids) {
    const products = [];
    for (let offset = 0; offset < ids.length; offset += 400) {
      const requests = [];
      for (let index = offset; index < Math.min(offset + 400, ids.length); index += 100) {
        requests.push(fetchCatalog({mode: 'ids', ids: ids.slice(index, index + 100).join(',')}));
      }
      const results = await Promise.all(requests);
      products.push(...results.flatMap(data => data.PRODUCTS));
    }
    return products;
  }
  window.shopFetchProductsByIds = fetchProductsByIds;

  /** Читает ограниченный список идентификаторов корзины и избранного. */
  function getSavedIds() {
    const ids = new Set();
    for (const key of ['z62_cart_v1', 'z62_favorites']) {
      try {
        const values = JSON.parse(localStorage.getItem(key) || '[]');
        if (!Array.isArray(values)) continue;
        values.forEach(value => {
          const id = Number(key === 'z62_cart_v1' ? value?.id : value);
          if (Number.isSafeInteger(id) && id > 0) ids.add(id);
        });
      } catch (error) {
        console.warn('Не удалось прочитать сохранённую подборку.');
      }
    }
    return [...ids];
  }

  /** Проверяет и загрузку скрипта, и завершение его инициализации. */
  function loadApplication() {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const timeout = setTimeout(() => { script.remove(); reject(new Error('Приложение не ответило')); }, 10000);
      script.src = '/assets/js/app.js?v=catalog-2';
      script.onload = () => {
        clearTimeout(timeout);
        if (window.SHOP_READY) resolve();
        else reject(new Error('Не удалось запустить приложение'));
      };
      script.onerror = () => { clearTimeout(timeout); script.remove(); reject(new Error('Не удалось загрузить приложение')); };
      document.body.append(script);
    });
  }

  /** Показывает загрузку и восстанавливает работу после сетевой ошибки. */
  async function loadCatalog() {
    if (loading) return;
    loading = true;
    app.setAttribute('aria-busy', 'true');
    app.querySelector('[data-loading]')?.remove();
    const status = document.createElement('div');
    status.className = 'container section';
    status.dataset.loading = '';
    status.setAttribute('role', 'status');
    status.innerHTML = '<h2>Загружаем каталог</h2><p>Получаем актуальные цены и наличие…</p>';
    app.append(status);
    let startingApplication = false;
    try {
      const ids = getSavedIds();
      const [data, saved] = await Promise.all([
        fetchCatalog({mode: 'bootstrap'}), fetchProductsByIds(ids),
      ]);
      const products = new Map([...data.PRODUCTS, ...saved].map(product => [product.id, product]));
      data.PRODUCTS = [...products.values()];
      window.CATALOG_DATA = data;
      startingApplication = true;
      await loadApplication();
    } catch (error) {
      const target = app.querySelector('[data-loading]') || status;
      if (!target.isConnected) app.append(target);
      target.innerHTML = '<h2>Каталог временно недоступен</h2><p>Проверьте подключение и попробуйте ещё раз. Сохранённая корзина останется в браузере.</p><button class="btn btn--primary" type="button">Повторить загрузку</button>';
      target.querySelector('button').addEventListener('click', () => startingApplication ? location.reload() : loadCatalog());
    } finally {
      app.setAttribute('aria-busy', 'false');
      loading = false;
    }
  }
  loadCatalog();
})();
