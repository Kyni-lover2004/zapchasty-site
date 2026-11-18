"""Товары и изображения; покупательские контакты не хранятся."""
import re
import uuid
from decimal import Decimal
from io import BytesIO
from urllib.parse import urlsplit
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


def validate_photo(file):
    """Проверяет размер и содержимое фотографии до сохранения."""
    if file.size > 15 * 1024 * 1024:
        raise ValidationError('Фото должно быть не больше 15 МБ.')
    try:
        file.seek(0)
        with Image.open(file) as image:
            if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 25_000_000:
                raise ValidationError('Нужны JPG, PNG или WebP до 25 мегапикселей.')
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValidationError('Файл не является поддерживаемой фотографией.') from error
    finally:
        file.seek(0)


class Category(models.Model):
    slug = models.SlugField('Код', unique=True)
    name = models.CharField('Название', max_length=120)
    icon = models.CharField('Иконка', max_length=20, choices=[(key,key) for key in ['display','battery','flex','camera','glass','back','charging','lower-board','tool']], default='tool')
    description = models.TextField('Описание', blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField('Название', max_length=250)
    slug = models.SlugField('Адрес товара', unique=True, max_length=250, default=uuid.uuid4)
    part = models.CharField('Артикул', unique=True, max_length=100)
    subtitle = models.CharField('Вариант / цвет / комплектация', max_length=250, blank=True)
    description = models.TextField(
        'Описание', blank=True,
        help_text='Обычный текст. Если оставить поле пустым, сайт покажет базовое описание детали.',
    )
    category = models.ForeignKey(Category, verbose_name='Категория', on_delete=models.PROTECT)
    brand = models.CharField('Бренд', max_length=100)
    device = models.CharField('Основная модель', max_length=150)
    compatibility = models.TextField('Совместимые модели', help_text='Одна модель на строку. Например: iPhone 11')
    price = models.PositiveIntegerField('Цена, ₽', validators=[MinValueValidator(1)])
    old_price = models.PositiveIntegerField('Цена до скидки, ₽', null=True, blank=True)
    stock = models.PositiveIntegerField('Остаток, шт.', default=0)
    warranty = models.CharField('Гарантия', max_length=150, blank=True)
    badge = models.CharField('Метка', max_length=30, blank=True)
    featured = models.BooleanField('На главной', default=False)
    active = models.BooleanField('Показывать на сайте', default=True)
    updated_at = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def clean(self):
        """Проверяет скидку и формат артикула новых карточек."""
        if self._state.adding and self.part and not re.fullmatch(r'z62-[0-9]{4}', self.part):
            raise ValidationError({'part': 'Введите артикул в формате z62-0000: строчные буквы и четыре цифры.'})
        if self.old_price and self.price and self.old_price <= self.price:
            raise ValidationError({'old_price': 'Цена до скидки должна быть выше текущей.'})

    def __str__(self):
        return f'{self.name} · {self.part}'

    @property
    def qr_code(self):
        return f'Z62:{self.pk}'


class ProductPartCounter(models.Model):
    next_number = models.PositiveIntegerField(default=0)

    def get_next_number(self):
        """Продолжает нумерацию с учётом ранее заданных артикулов."""
        last_part = Product.objects.filter(part__regex=r'^z62-[0-9]{4}$').order_by('-part').values_list('part', flat=True).first()
        return max(self.next_number, int(last_part[4:]) + 1) if last_part else self.next_number


class Receipt(models.Model):
    number = models.CharField('Номер накладной', max_length=100)
    supplier = models.CharField('Поставщик', max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(Receipt, related_name='lines', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    expected = models.PositiveIntegerField()
    received = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['receipt', 'product'], name='unique_receipt_product'),
            models.CheckConstraint(condition=models.Q(expected__gt=0), name='receipt_expected_positive'),
        ]


class Sale(models.Model):
    class Payment(models.TextChoices):
        CASH = 'cash', 'Наличные'
        CARD = 'card', 'Карта'
        TRANSFER = 'transfer', 'Перевод'

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    payment_method = models.CharField(max_length=12, choices=Payment.choices, blank=True)
    cashier_name = models.CharField(max_length=300, blank=True)

    @property
    def number(self):
        return f'r62-{self.pk - 1:04d}'


class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, related_name='lines', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    part = models.CharField(max_length=100)
    name = models.CharField(max_length=250)
    subtitle = models.CharField(max_length=250, blank=True)
    price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total(self):
        return self.price * self.quantity

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sale', 'product'], name='unique_sale_product'),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='sale_line_quantity_positive'),
        ]


class SaleRefund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, related_name='refunds', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    employee_name = models.CharField(max_length=150)


class SaleRefundLine(models.Model):
    refund = models.ForeignKey(SaleRefund, related_name='lines', on_delete=models.PROTECT)
    sale_line = models.ForeignKey(SaleLine, related_name='refund_lines', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['refund', 'sale_line'], name='unique_refund_sale_line'),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='refund_quantity_positive'),
        ]


class Expense(models.Model):
    class Category(models.TextChoices):
        PURCHASE = 'purchase', 'Закупка товара'
        DELIVERY = 'delivery', 'Доставка'
        RENT = 'rent', 'Аренда'
        SUPPLIES = 'supplies', 'Расходники'
        OTHER = 'other', 'Прочее'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField('Сумма, ₽', max_digits=12, decimal_places=2,
                                 validators=[MinValueValidator(Decimal('0.01'))])
    category = models.CharField('Категория', max_length=12, choices=Category.choices)
    description = models.CharField('На что или кому', max_length=250)
    payment_method = models.CharField('Способ оплаты', max_length=12, choices=Sale.Payment.choices, blank=True)
    spent_at = models.DateTimeField('Дата и время расхода', db_index=True)
    employee_name = models.CharField(max_length=150)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='expense_amount_positive')]


class StockMovement(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = 'receipt', 'Приход'
        ISSUE = 'issue', 'Выдача'
        WRITE_OFF = 'write_off', 'Списание'
        COUNT = 'count', 'Пересчёт'
        SALE_RETURN = 'sale_return', 'Возврат в остаток'

    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    receipt = models.ForeignKey(Receipt, null=True, blank=True, on_delete=models.PROTECT)
    sale = models.ForeignKey(Sale, related_name='movements', null=True, blank=True, on_delete=models.PROTECT)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    employee_name = models.CharField(max_length=150)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    change = models.IntegerField()
    balance = models.PositiveIntegerField()
    reason = models.CharField(max_length=250, blank=True)
    operation_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']
        permissions = [('operate_stock', 'Может принимать и учитывать товары на складе')]
        indexes = [models.Index(fields=['product', '-id'], name='stock_product_latest')]
        constraints = [models.UniqueConstraint(fields=['product', 'operation_id'], name='unique_stock_operation')]


class Photo(models.Model):
    product = models.ForeignKey(Product, related_name='photos', on_delete=models.CASCADE)
    image = models.ImageField('Фото с устройства', upload_to='products/%Y/%m/', validators=[validate_photo])
    position = models.PositiveIntegerField('Порядок', default=0, help_text='Фото с наименьшим номером — главное.')

    class Meta:
        ordering = ['position', 'id']
        verbose_name = 'Фотография'
        verbose_name_plural = 'Фотографии'

    def __str__(self):
        return f'Фото {self.position + 1}'

    def save(self, *args, **kwargs):
        """Уменьшает новое фото, удаляет метаданные и сохраняет WebP."""
        if self.image and not self.image._committed:
            validate_photo(self.image)
            with Image.open(self.image) as original:
                image = ImageOps.exif_transpose(original).convert('RGB')
                image.thumbnail((1600, 1600))
                output = BytesIO()
                image.save(output, 'WEBP', quality=85)
            self.image.save(f'{uuid.uuid4().hex}.webp', ContentFile(output.getvalue()), save=False)
        super().save(*args, **kwargs)


class Specification(models.Model):
    product = models.ForeignKey(Product, related_name='specifications', on_delete=models.CASCADE)
    name = models.CharField('Характеристика', max_length=100)
    value = models.CharField('Значение', max_length=250)

    class Meta:
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'
        constraints = [models.UniqueConstraint(fields=['product','name'], name='unique_product_spec')]

    def __str__(self):
        return f'{self.name}: {self.value}'


class StoreSettings(models.Model):
    address = models.CharField('Адрес самовывоза', max_length=250, default='Рязань, ул. Татарская, 24 (предварительно)')
    hours = models.CharField('Часы работы', max_length=150, default='Пн–Сб, 9:00–19:00')
    phone = models.CharField(
        'Телефон магазина', max_length=40, default='+7 (4912) 00-00-62', blank=True,
        validators=[RegexValidator(r'\A\+?[0-9 ()-]+\Z', 'Введите номер телефона с цифрами.')],
    )
    telegram = models.URLField('Telegram', default='https://t.me/rznmastershop62', blank=True,
                              help_text='Ссылка на чат, например https://t.me/rznmastershop62.')
    vk = models.URLField('ВКонтакте', blank=True, help_text='Ссылка на сообщения магазина в VK.')

    class Meta:
        verbose_name = 'Контакты магазина'
        verbose_name_plural = 'Настройки магазина'
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='single_store_settings')]

    def __str__(self):
        return 'Контакты и соцсети'

    def clean(self):
        """Проверяет, что ссылки ведут на поддерживаемые сайты."""
        errors = {}
        for field, hosts in [('telegram', {'t.me'}), ('vk', {'vk.com', 'vk.me', 'www.vk.com'})]:
            value = getattr(self, field)
            if not value:
                continue
            try:
                url = urlsplit(value)
                valid = url.scheme == 'https' and url.netloc.lower() in hosts
                if field == 'telegram':
                    valid = valid and bool(re.fullmatch(r'/[A-Za-z0-9_]+/?', url.path)) and not (url.query or url.fragment)
            except ValueError:
                valid = False
            if not valid:
                errors[field] = 'Укажите полную HTTPS-ссылку на чат магазина.'
        if self.phone and not 7 <= len(re.sub(r'\D', '', self.phone)) <= 15:
            errors['phone'] = 'В номере должно быть от 7 до 15 цифр.'
        if errors:
            raise ValidationError(errors)
