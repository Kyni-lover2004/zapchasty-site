"""Проверки постраничной выдачи, поиска и публичных карточек."""
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings

from .models import Category, Product


class PublicCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Создаёт каталог больше одной страницы и скрытый товар."""
        category = Category.objects.create(slug='displays', name='Дисплеи')
        cls.products = Product.objects.bulk_create([
            Product(name=f'Экран iPhone {number}', part=f'z62-{number:04d}', slug=f'iphone-{number}',
                    category=category, brand='Apple', device=f'iPhone {number}', compatibility=f'iPhone {number}\niPhone {number} Pro',
                    price=1000 + number, stock=number % 4, featured=number < 3)
            for number in range(1, 32)
        ])
        cls.hidden = Product.objects.create(name='Скрытый экран', part='hidden', slug='hidden', category=category,
            brand='Apple', device='iPhone 1', compatibility='iPhone 1', price=1, stock=9, active=False)

    def test_bootstrap_is_bounded_but_facets_count_all_products(self):
        """Начальная выдача ограничена, а счётчики учитывают весь каталог."""
        data = self.client.get('/api/catalog/').json()
        self.assertEqual(len(data['PRODUCTS']), 12)
        self.assertEqual(data['FACETS']['total'], 31)
        self.assertEqual(data['FACETS']['categories']['displays'], 31)
        self.assertTrue(data['SERVER_CATALOG'])

    def test_pages_do_not_overlap_and_never_publish_hidden_products(self):
        """Страницы ограничены 24 карточками и имеют точный общий счётчик."""
        first = self.client.get('/api/catalog/', {'mode': 'search'}).json()
        second = self.client.get('/api/catalog/', {'mode': 'search', 'page': 2}).json()
        self.assertEqual((len(first['PRODUCTS']), len(second['PRODUCTS']), first['total']), (24, 7, 31))
        self.assertFalse(set(item['id'] for item in first['PRODUCTS']) & set(item['id'] for item in second['PRODUCTS']))
        self.assertNotIn(self.hidden.pk, [item['id'] for item in first['PRODUCTS'] + second['PRODUCTS']])

    def test_search_supports_synonyms_articles_and_compact_model(self):
        """Сохраняются поиск по артикулу, слитной модели и названию детали."""
        for query in ['z62-0001', 'iphone1', 'дисплей iphone 1']:
            with self.subTest(query=query):
                data = self.client.get('/api/catalog/', {'mode': 'search', 'q': query}).json()
                self.assertGreater(data['total'], 0)
                self.assertIn(self.products[0].pk, [item['id'] for item in data['PRODUCTS']])

    def test_filters_sort_and_exact_compatibility(self):
        """Точная модель не захватывает соседние номера, цены нормализуются."""
        data = self.client.get('/api/catalog/', {'mode': 'search', 'model': 'iPhone 1', 'brand': 'Apple'}).json()
        self.assertEqual([item['id'] for item in data['PRODUCTS']], [self.products[0].pk])
        data = self.client.get('/api/catalog/', {'mode': 'search', 'min': '1010', 'max': '1001', 'stock': '1', 'sort': 'price-desc'}).json()
        self.assertTrue(data['PRODUCTS'])
        prices = [item['price'] for item in data['PRODUCTS']]
        self.assertEqual(prices, sorted(prices, reverse=True))
        self.assertTrue(all(1001 <= item['price'] <= 1010 and item['stock'] > 0 for item in data['PRODUCTS']))

    def test_saved_items_refresh_price_stock_and_publication(self):
        """Повторная проверка корзины получает изменения из базы."""
        product = self.products[0]
        Product.objects.filter(pk=product.pk).update(price=7777, stock=1)
        data = self.client.get('/api/catalog/', {'mode': 'ids', 'ids': f'{product.pk},{self.hidden.pk}'}).json()
        self.assertEqual([(item['id'], item['price'], item['stock']) for item in data['PRODUCTS']], [(product.pk, 7777, 1)])
        Product.objects.filter(pk=product.pk).update(active=False)
        self.assertEqual(self.client.get('/api/catalog/', {'mode': 'ids', 'ids': product.pk}).json()['PRODUCTS'], [])
        self.assertEqual(self.client.get('/api/catalog/', {'mode': 'ids', 'ids': '1 OR 1=1'}).status_code, 400)

    @override_settings(SHOP_PUBLIC_URL='https://shop.example.ru')
    def test_product_has_real_url_metadata_fallback_and_escaped_content(self):
        """Карточка читается без JavaScript и не позволяет внедрить HTML."""
        Product.objects.filter(pk=self.products[0].pk).update(name='Экран <script>alert(1)</script>')
        response = self.client.get('/product/iphone-1/')
        self.assertContains(response, 'https://shop.example.ru/product/iphone-1/')
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, 'data-public-fallback')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(self.client.get('/product/hidden/').status_code, 404)

    def test_sitemap_models_and_health_do_not_leak_private_data(self):
        """Индексация и подбор исключают скрытые карточки, health скрывает ошибку БД."""
        sitemap = self.client.get('/sitemap.xml').content.decode()
        self.assertIn('/product/iphone-1/', sitemap)
        self.assertNotIn('/product/hidden/', sitemap)
        self.assertNotIn('/admin', sitemap)
        models = self.client.get('/api/catalog/', {'mode': 'models', 'brand': 'Apple', 'q': 'iPhone 1'}).json()
        self.assertTrue(models['models'])
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
        with patch('shop.views.connection.cursor', side_effect=DatabaseError('private password')):
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'private password', response.content)
