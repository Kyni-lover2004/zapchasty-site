"""Проверки каталога, доступа и обработки изображений на PostgreSQL."""
import tempfile
import uuid
from datetime import datetime, timezone as utc_timezone
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.test import TestCase, override_settings
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Category, Expense, Product, Photo, Sale, SaleLine, SaleRefund, validate_photo

class CatalogTests(TestCase):
    def setUp(self):
        """Создаёт минимальный товар для независимых проверок."""
        category = Category.objects.create(slug='displays',name='Дисплеи')
        self.product = Product.objects.create(name='Экран', part='DSP-TEST', category=category, brand='Apple', device='iPhone 11', compatibility='iPhone 11', price=1000, stock=2)

    def test_catalog_tracks_edits_and_hiding(self):
        """Витрина получает текущую цену и исключает скрытые позиции."""
        self.product.price = 1250
        self.product.save()
        response = self.client.get('/api/catalog/')
        self.assertEqual(response.json()['PRODUCTS'][0]['price'],1250)
        self.product.active = False
        self.product.save()
        self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'],[])

    def test_row_delete_requires_permission_and_confirmation(self):
        """Открытие ссылки оставляет товар, подтверждение удаляет его при наличии права."""
        editor = User.objects.create_user('catalog-editor', is_staff=True)
        editor.user_permissions.add(Permission.objects.get(codename='change_product'))
        self.client.force_login(editor)
        list_url = '/admin/shop/product/'
        delete_url = f'{list_url}{self.product.pk}/delete/'
        self.assertNotContains(self.client.get(list_url), 'product-delete-link')
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 403)

        editor.user_permissions.add(Permission.objects.get(codename='delete_product'))
        self.assertContains(self.client.get(list_url), f'href="{delete_url}"')
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_anonymous_cannot_edit(self):
        """Анонимный посетитель не может записывать каталог или открыть админку."""
        self.assertEqual(self.client.post('/api/catalog/',{}).status_code,405)
        self.assertEqual(self.client.get('/admin/shop/product/').status_code,302)
        user = User.objects.create_user('buyer',password='test-secret-long')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/shop/product/').status_code,302)
        self.assertEqual(self.client.get('/.local/env').status_code,404)

    def test_upload_is_reencoded_and_published(self):
        """Фото сохраняется на диск в WebP и появляется в публичном API."""
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            output = BytesIO()
            Image.new('RGB',(2000,1000),'blue').save(output,'JPEG')
            photo = Photo.objects.create(product=self.product,image=SimpleUploadedFile('test.jpg',output.getvalue(),content_type='image/jpeg'))
            with Image.open(photo.image.path) as image:
                self.assertEqual(image.format,'WEBP')
                self.assertEqual(image.size,(1600,800))
            self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'][0]['images'],[photo.image.url])

    def test_invalid_image_and_price_are_rejected(self):
        """Нельзя загрузить HTML как фото или задать некорректную скидку."""
        with self.assertRaises(ValidationError):
            validate_photo(SimpleUploadedFile('photo.jpg',b'<script>alert(1)</script>'))
        self.product.old_price=500
        with self.assertRaises(ValidationError):
            self.product.full_clean()

    def test_admin_form_saves_product(self):
        """Проверяет реальную форму администратора с вложенными строками."""
        user = User.objects.create_superuser('editor',password='test-secret-long')
        self.client.force_login(user)
        description = 'Экран в сборе.\nПодключите модуль для проверки до установки.'
        response = self.client.post(f'/admin/shop/product/{self.product.pk}/change/', {
            'name':'Новый экран', 'slug':self.product.slug, 'part':'z62-0999', 'category':self.product.category_id,
            'price':'1490', 'stock':'5', 'brand':'Apple', 'device':'iPhone 11', 'compatibility':'iPhone 11', 'active':'on',
            'description': description,
            'photos-TOTAL_FORMS':'0', 'photos-INITIAL_FORMS':'0', 'photos-MIN_NUM_FORMS':'0', 'photos-MAX_NUM_FORMS':'1000',
            'specifications-TOTAL_FORMS':'0', 'specifications-INITIAL_FORMS':'0', 'specifications-MIN_NUM_FORMS':'0', 'specifications-MAX_NUM_FORMS':'1000', '_save':'Сохранить'
        })
        self.assertEqual(response.status_code,302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price,1490)
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(self.product.part, 'DSP-TEST')
        self.assertEqual(self.product.description, description)
        self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'][0]['description'], description)

    def test_admin_assigns_sequential_articles_to_new_products(self):
        """Проверяет предпросмотр, выдачу при сохранении и отсутствие повторной выдачи."""
        self.client.force_login(User.objects.create_superuser('article-editor'))
        url = '/admin/shop/product/add/'
        self.assertContains(self.client.get(url), 'z62-0000')
        fields = {
            'name': 'Первый товар', 'slug': 'automatic-part-first', 'part': 'z62-0999', 'category': self.product.category_id,
            'price': 1000, 'brand': 'Apple', 'device': 'iPhone 11', 'compatibility': 'iPhone 11',
            'photos-TOTAL_FORMS': '0', 'photos-INITIAL_FORMS': '0',
            'specifications-TOTAL_FORMS': '0', 'specifications-INITIAL_FORMS': '0',
            '_addanother': 'Сохранить и добавить другой объект',
        }
        self.assertEqual(self.client.post(url, {**fields, 'price': 0}).status_code, 200)
        response = self.client.post(url, fields)
        if response.status_code == 200:
            self.fail(str(response.context['adminform'].form.errors))
        self.assertRedirects(response, url)
        first = Product.objects.get(name='Первый товар')
        self.assertEqual(first.part, 'z62-0000')
        first.delete()
        self.assertContains(self.client.get(url), 'z62-0001')
        self.assertRedirects(self.client.post(url, {**fields, 'name': 'Второй товар', 'slug': 'automatic-part-second'}), url)
        self.assertEqual(Product.objects.get(name='Второй товар').part, 'z62-0001')

    def test_store_settings_edit_reaches_checkout_data(self):
        """Сохранённые контакты попадают в тот же API, из которого читает витрина."""
        user = User.objects.create_superuser('store-editor', password='test-secret-long')
        self.client.force_login(user)
        response = self.client.post('/admin/shop/storesettings/1/change/', {
            'address': 'Рязань, новый адрес',
            'hours': '10:00–18:00',
            'phone': '+7 (4912) 12-34-56',
            'telegram': 'https://t.me/test_shop',
            'vk': 'https://vk.me/test_shop',
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        data = self.client.get('/api/catalog/').json()
        self.assertEqual(data['CONTACTS']['addressFull'], 'Рязань, новый адрес')
        self.assertEqual(data['CONTACTS']['phoneHref'], '+74912123456')
        self.assertEqual(data['SOCIAL_LINKS']['telegram'], 'https://t.me/test_shop')
        self.assertEqual(data['SOCIAL_LINKS']['vk'], 'https://vk.me/test_shop')


class WarehouseTests(TestCase):
    def setUp(self):
        """Создаёт две похожие позиции, чтобы проверять ошибки при сканировании."""
        category = Category.objects.create(slug='screens', name='Дисплеи')
        fields = dict(category=category, brand='Apple', device='iPhone 11', price=1000)
        self.product = Product.objects.create(name='Экран In-Cell', part='z62-0000', stock=2, **fields)
        self.other = Product.objects.create(name='Экран OLED', part='z62-0001', **fields)
        self.employee = User.objects.create_user('operator', is_staff=True)
        self.employee.user_permissions.add(Permission.objects.get(codename='operate_stock'))
        self.client.force_login(self.employee)

    def test_receipt_only_changes_catalog_once_when_posted(self):
        """Проверяет приход с недостачей, повтором проведения и чужим QR."""
        response = self.client.post('/warehouse/', {'number': 'П-001'})
        url = response['Location']
        response = self.client.get(url)
        self.assertContains(response, 'Сверка сканером')
        self.client.post(url, {'action': 'add', 'code': self.product.part, 'quantity': 3})
        response = self.client.post(url, {'action': 'scan', 'code': self.other.qr_code, 'quantity': 1}, follow=True)
        self.assertContains(response, 'отсутствует в этой накладной')
        self.client.post(url, {'action': 'scan', 'code': self.product.qr_code, 'quantity': 2})
        response = self.client.post(url, {'action': 'post'}, follow=True)
        self.assertContains(response, 'Есть расхождения')
        self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'][0]['stock'], 2)

        response = self.client.post(url, {'action': 'post', 'accept_difference': 'on'}, follow=True)
        self.assertContains(response, 'Накладная проведена')
        response = self.client.post(url, {'action': 'post', 'accept_difference': 'on'}, follow=True)
        self.assertContains(response, 'Эта накладная уже проведена')
        self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'][0]['stock'], 4)
        self.assertEqual(self.product.stockmovement_set.count(), 1)
        self.assertEqual(self.other.stockmovement_set.count(), 0)

    def test_staff_without_warehouse_permission_cannot_operate(self):
        """Статуса сотрудника самого по себе для складских данных мало."""
        self.client.logout()
        self.assertEqual(self.client.get('/warehouse/').status_code, 302)
        self.client.force_login(User.objects.create_user('editor', is_staff=True))
        self.assertEqual(self.client.get('/warehouse/stock/').status_code, 403)
        self.assertEqual(self.client.post('/warehouse/', {'number': 'П-001'}).status_code, 403)

    def test_print_labels_and_find_stock_by_qr(self):
        """Проверяет печать нужного количества этикеток и переход из сканера."""
        url = f'/warehouse/labels/{self.product.pk}/'
        response = self.client.get(url, {'copies': 3})
        self.assertContains(response, 'class="warehouse-label"', count=3)
        self.assertContains(response, self.product.part)
        response = self.client.get(f'{url}qr/')
        self.assertEqual(response.headers['Content-Type'], 'image/svg+xml')
        self.assertContains(response, '<svg')
        response = self.client.get('/warehouse/stock/', {'q': self.product.qr_code})
        self.assertRedirects(response, f'/warehouse/stock/{self.product.pk}/')

    def test_stock_movements_trace_employee_and_prevent_duplicate_or_negative(self):
        """Проверяет повтор отправки, запрет отрицательного остатка и пересчёт в ноль."""
        url = f'/warehouse/stock/{self.product.pk}/'
        form = self.client.get(url).context['form']
        data = {
            'kind': 'issue', 'quantity': 1, 'reason': 'Заказ 1', 'operation_id': form['operation_id'].value(),
            'previous_balance': form['previous_balance'].value(),
        }
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertContains(self.client.post(url, data), 'Эта операция уже проведена')
        form = self.client.get(url).context['form']
        data.update(operation_id=form['operation_id'].value(), kind='write_off', quantity=2, reason='Брак')
        self.assertContains(self.client.post(url, data), 'На складе только 1 шт.')
        data.update(kind='count', quantity=0, reason='Пересчёт')
        self.assertContains(self.client.post(url, data), 'Остаток изменился')
        data['previous_balance'] = form['previous_balance'].value()
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(self.product.stockmovement_set.count(), 2)
        movement = self.product.stockmovement_set.first()
        self.assertEqual((movement.employee, movement.change, movement.balance), (self.employee, -1, 0))

    def test_sale_scans_change_stock_and_print_the_saved_order(self):
        """Проверяет списание, повтор запроса, отмену скана и накладную."""
        sales_url = '/warehouse/sales/'
        sale_url = self.client.post(sales_url)['Location']
        sale = self.client.get(sale_url)
        self.assertContains(sale, 'r62-0000')
        next_url = self.client.post(sales_url)['Location']
        self.assertContains(self.client.get(next_url), 'r62-0001')

        scan = {'action': 'scan', 'code': self.product.part, 'operation_id': sale.context['operation_id']}
        self.client.post(sale_url, scan)
        repeat = self.client.post(sale_url, scan, follow=True)
        self.assertContains(repeat, 'Эта операция уже учтена')
        self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'][0]['stock'], 1)

        self.product.price = 1200
        self.product.save(update_fields=['price'])
        scan.update(code=self.product.qr_code, operation_id=repeat.context['operation_id'])
        after_scan = self.client.post(sale_url, scan, follow=True)
        self.assertEqual(after_scan.context['units'], 2)
        self.assertEqual(after_scan.context['total'], 2000)
        self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'][0]['stock'], 0)

        scan['operation_id'] = after_scan.context['operation_id']
        rejected = self.client.post(sale_url, scan, follow=True)
        self.assertContains(rejected, 'товара нет в наличии')
        self.assertEqual(rejected.context['units'], 2)
        self.client.post(sale_url, {
            'action': 'undo', 'line': rejected.context['lines'][0].pk,
            'operation_id': rejected.context['operation_id'],
        })
        self.assertEqual(self.client.get('/api/catalog/').json()['PRODUCTS'][0]['stock'], 1)

        self.client.post(sale_url, {'action': 'close'})
        printed = self.client.get(sale_url + 'print/')
        self.assertContains(printed, 'Накладная № r62-0000')
        self.assertContains(printed, self.product.part)
        self.assertContains(printed, '1000 ₽')
        self.assertNotContains(printed, 'Вернуть 1 шт.')
        after_close = self.client.post(sale_url, scan, follow=True)
        self.assertContains(after_close, 'Заказ уже завершён')
        self.assertEqual(self.product.stockmovement_set.count(), 3)
        self.assertContains(self.client.get(f'/warehouse/stock/{self.product.pk}/'), f'href="{sale_url}"')

    def test_sales_report_uses_moscow_day_and_records_each_expense_once(self):
        """Выручка привязана к завершению, копейки и повтор отправки учтены."""
        sales_url = '/warehouse/sales/'
        report_url = sales_url + 'report/'
        order_url = self.client.post(sales_url)['Location']
        page = self.client.get(order_url)
        self.client.post(order_url, {
            'action': 'scan', 'code': self.product.part, 'operation_id': page.context['operation_id'],
        })
        self.assertEqual(self.client.get(sales_url).context['totals']['revenue'], 0)
        self.client.post(order_url, {'action': 'close', 'payment_method': 'card'})
        sale = Sale.objects.get()
        self.assertEqual(sale.payment_method, 'card')
        Sale.objects.filter(pk=sale.pk).update(
            created_at=datetime(2026, 1, 1, 20, 0, tzinfo=utc_timezone.utc),
            closed_at=datetime(2026, 1, 1, 22, 15, tzinfo=utc_timezone.utc),
        )

        expense_data = {
            'spent_at': '2026-01-02T01:20', 'category': 'purchase',
            'description': 'Детали у поставщика', 'amount': '120.50', 'entry_id': uuid.uuid4(),
        }
        self.assertRedirects(self.client.post(report_url, expense_data), report_url + '?day=2026-01-02#report-day')
        self.assertEqual(self.client.post(report_url, expense_data).status_code, 302)
        self.assertEqual(Expense.objects.count(), 1)
        response = self.client.get(report_url, {'day': '2026-01-02'})
        self.assertEqual(response.context['totals'], {
            'revenue': 1000, 'expenses': Decimal('120.50'), 'refunds': 0, 'balance': Decimal('879.50'),
        })
        self.assertContains(response, 'Детали у поставщика')
        self.assertContains(response, 'Карта')
        self.assertContains(response, f'href="{order_url}"')
        self.assertEqual(response.context['entries'][0]['expense'].employee_name, self.employee.username)
        self.assertEqual(self.client.get(report_url, {'day': '2026-01-01'}).context['totals']['revenue'], 0)

        expense_data.update(entry_id=uuid.uuid4(), amount='0')
        self.assertEqual(self.client.post(report_url, expense_data).status_code, 200)
        self.assertEqual(Expense.objects.count(), 1)

    def test_sales_return_restocks_partial_quantities_and_reduces_daily_balance(self):
        """Проверяет возврат нескольких позиций по ценам заказа и отчёт по дате возврата."""
        sale = Sale.objects.create(closed_at=datetime(2026, 1, 2, 10, tzinfo=utc_timezone.utc))
        first = SaleLine.objects.create(sale=sale, product=self.product, name=self.product.name,
                                        part=self.product.part, price=900, quantity=2)
        second = SaleLine.objects.create(sale=sale, product=self.other, name=self.other.name,
                                         part=self.other.part, price=400)
        url = '/warehouse/returns/?order=' + sale.number
        response = self.client.get(url)
        self.assertContains(response, self.product.part)
        data = {'operation_id': uuid.uuid4(), f'quantity_{first.pk}': 1, f'quantity_{second.pk}': 1}
        self.assertRedirects(self.client.post(url, data), url)

        self.product.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.product.stock, self.other.stock), (3, 1))
        self.client.post(url, {**data, f'quantity_{second.pk}': 0})
        self.client.post(url, {'operation_id': uuid.uuid4(), f'quantity_{first.pk}': 2})
        self.assertEqual(SaleRefund.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

        report = self.client.get('/warehouse/sales/report/', {'day': timezone.localdate().isoformat()})
        self.assertEqual(report.context['totals']['refunds'], 1300)
        self.assertEqual(report.context['totals']['balance'], -1300)
        self.assertContains(report, f'href="{url}"')
        original_day = self.client.get('/warehouse/sales/report/', {'day': '2026-01-02'})
        self.assertEqual(original_day.context['totals']['revenue'], 2200)
        self.assertEqual(original_day.context['totals']['refunds'], 0)
