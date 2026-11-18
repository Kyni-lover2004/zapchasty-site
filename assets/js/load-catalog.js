/** Загружает актуальную витрину; при сбое не подменяет её демо-данными. */
(async function loadCatalog() {
  try {
    const response = await fetch('/api/catalog/', {cache: 'no-store'});
    if (!response.ok) throw new Error('Каталог недоступен');
    window.CATALOG_DATA = await response.json();
    const script = document.createElement('script');
    script.src = 'assets/js/app.js?v=favorite-heart';
    document.body.append(script);
  } catch (error) {
    document.getElementById('app').innerHTML = '<div class="container section"><h1>Каталог временно недоступен</h1><p>Не удалось загрузить товары. Обновите страницу через минуту.</p><button class="btn btn--primary" onclick="location.reload()">Обновить</button></div>';
  }
})();
