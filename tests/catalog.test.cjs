const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

/** Загружает клиентскую логику без запуска DOM-интерфейса. */
function loadShop(stored = {}) {
  const context = vm.createContext({
    window: {}, console, URLSearchParams, Intl, URL, crypto: require('node:crypto').webcrypto,
    document: {getElementById: () => ({}), addEventListener() {}, querySelector: () => null, querySelectorAll: () => []},
    localStorage: {getItem: key => stored[key] || null, removeItem: key => { delete stored[key]; }, setItem: (key,value) => { stored[key] = value; }}
  });
  vm.runInContext(fs.readFileSync('assets/js/data.js','utf8'), context);
  let source = fs.readFileSync('assets/js/app.js','utf8');
  source = source.slice(0, source.indexOf('  /* ---------- Запуск ---------- */'));
  source += 'window.testShop = {readCart, filterProducts, filtersFromQuery, buildUrl, getSocialUrl, clearLegacyCustomerData, buildCartMessage, buildTelegramLink, getProductDescription, reconcileCart, cartItems, refreshCart};})();';
  vm.runInContext(source, context);
  return {shop: context.window.testShop, context};
}

test('точная совместимость и поиск артикула', () => {
  const {shop} = loadShop();
  const state = shop.filtersFromQuery(new URLSearchParams({model:'iPhone 11'}));
  const products = shop.filterProducts(state);
  assert.equal(products.length,7);
  assert.ok(products.every(product => product.compat.includes('iPhone 11')));
  assert.equal(shop.filterProducts(shop.filtersFromQuery(new URLSearchParams({q:'DSP-IP11'})))[0].id,1);
  assert.ok(shop.buildUrl('/catalog',state).includes('model=iPhone+11'));
});

test('описание дисплея соответствует варианту, а текст продавца имеет приоритет', () => {
  const {shop} = loadShop();
  const lcd = {category: 'displays', subtitle: 'LCD', specs: {'Тип матрицы': 'LCD'}};
  assert.doesNotMatch(shop.getProductDescription(lcd), /In-Cell|IC Transfer/);
  assert.match(shop.getProductDescription({...lcd, subtitle: 'In‑Cell'}), /^In-Cell.*IC Transfer/);
  assert.match(shop.getProductDescription({...lcd, subtitle: 'AMOLED'}), /^OLED.*рамки/);
  assert.match(shop.getProductDescription({...lcd, subtitle: 'OLED, оригинал'}), /^Оригинальный дисплей/);
  assert.equal(shop.getProductDescription({...lcd, description: 'Текст продавца\nВторая строка'}), 'Текст продавца\nВторая строка');
});

test('корзина ограничивает количество остатком и удаляет повреждённые записи', () => {
  const {shop} = loadShop({z62_cart_v1: JSON.stringify([{id:1,qty:999},{id:2,qty:1.8},{id:999,qty:2},{id:1,qty:'bad'},{id:3,qty:2}])});
  const cart = shop.readCart();
  assert.equal(cart[0].qty,6);
  assert.equal(cart[1].qty,1);
  assert.ok(cart.every(item => Number.isInteger(item.qty) && item.qty > 0));
});

test('наличие, цены и сортировка работают вместе', () => {
  const {shop} = loadShop();
  const products = shop.filterProducts(shop.filtersFromQuery(new URLSearchParams({stock:'1',min:'1000',max:'5000',sort:'price-desc'})));
  assert.ok(products.length);
  assert.ok(products.every(product => product.stock > 0 && product.price >= 1000 && product.price <= 5000));
  assert.ok(products.every((product,index) => !index || products[index-1].price >= product.price));
});

test('прежние контакты и заказы удаляются, корзина сохраняется', () => {
  const stored = {z62_customer_v1: '{"name":"Test"}', z62_orders_v1:'[]', z62_cart_v1:'[]'};
  const {shop} = loadShop(stored);
  shop.clearLegacyCustomerData();
  assert.equal(stored.z62_customer_v1,undefined);
  assert.equal(stored.z62_orders_v1,undefined);
  assert.equal(stored.z62_cart_v1,'[]');
});

test('пустые и небезопасные ссылки не активируются', () => {
  const {shop,context} = loadShop();
  assert.equal(shop.getSocialUrl('vk'),'');
  context.window.CATALOG_DATA.SOCIAL_LINKS.vk = 'javascript:alert(1)';
  assert.equal(shop.getSocialUrl('vk'),'');
  context.window.CATALOG_DATA.SOCIAL_LINKS.vk = 'https://vk.com/example';
  assert.equal(shop.getSocialUrl('vk'),'https://vk.com/example');
});

test('Telegram получает точный состав, количество и сумму без контактных полей', () => {
  const {shop,context} = loadShop();
  const product = context.window.CATALOG_DATA.PRODUCTS[0];
  const message = shop.buildCartMessage([{product,qty:2}]);
  const link = shop.buildTelegramLink(message);
  const url = new URL(link.url);
  assert.equal(url.hostname,'t.me');
  assert.equal(url.pathname,'/rznmastershop62');
  assert.equal(url.searchParams.get('text'),message);
  assert.ok(message.includes(product.part));
  assert.ok(message.includes('2 шт.'));
  assert.match(message,/Итого: 4\s980 ₽/);
  assert.equal(link.manual,false);
  assert.ok(!message.includes('Телефон:'));
});

test('пустая корзина открывает обычный чат, длинный заказ не обрезается', () => {
  const {shop} = loadShop();
  assert.equal(shop.buildCartMessage([]),'');
  assert.equal(shop.buildTelegramLink('').url,'https://t.me/rznmastershop62');
  const long = shop.buildTelegramLink('Деталь '.repeat(1000));
  assert.equal(long.manual,true);
  assert.equal(long.url,'https://t.me/rznmastershop62');
});

test('проверка корзины сообщает новую цену, уменьшает количество и убирает скрытые товары', () => {
  const stored = {z62_cart_v1: JSON.stringify([{id:1,qty:5},{id:2,qty:1}])};
  const {shop,context} = loadShop(stored);
  const product = {...context.window.CATALOG_DATA.PRODUCTS[0], price:5000, stock:2};
  const changes = shop.reconcileCart([product]);
  assert.equal(changes.length,3);
  assert.deepEqual(JSON.parse(stored.z62_cart_v1),[{id:1,qty:2}]);
  const message = shop.buildCartMessage(shop.cartItems());
  assert.match(message,/Итого: 10\s000 ₽/);
  assert.match(changes.join(' '),/цена изменилась/);
  assert.match(changes.join(' '),/больше недоступен/);
});

test('сбой проверки не удаляет корзину и не разрешает использовать старую цену', async () => {
  const stored = {z62_cart_v1: JSON.stringify([{id:1,qty:2}])};
  const {shop,context} = loadShop(stored);
  context.window.shopFetchProductsByIds = async () => { throw new Error('offline'); };
  await assert.rejects(shop.refreshCart(),/offline/);
  assert.deepEqual(JSON.parse(stored.z62_cart_v1),[{id:1,qty:2}]);
  assert.equal(shop.cartItems()[0].product.price,2490);
  context.window.shopFetchProductsByIds = async () => [{...context.window.CATALOG_DATA.PRODUCTS[0],price:3000}];
  const changes = await shop.refreshCart();
  assert.match(changes.join(' '),/цена изменилась/);
  assert.equal(shop.cartItems()[0].product.price,3000);
});
