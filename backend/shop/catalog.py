"""Ограниченные выборки публичного каталога и серверный поиск."""
import re

from django.db.models import Case, Count, F, Func, IntegerField, TextField, Value, When
from django.db.models.functions import Concat, Greatest, Replace

from .models import Product

SYNONYMS = {
    'акб': ['аккумулятор', 'батарея'], 'аккумулятор': ['акб', 'батарея'],
    'батарея': ['акб', 'аккумулятор'], 'экран': ['дисплей', 'тачскрин'],
    'дисплей': ['экран', 'тачскрин'], 'тачскрин': ['дисплей', 'экран'],
    'зарядка': ['разъем', 'шлейф'], 'разъем': ['зарядка'],
    'стекло': ['стекла', 'пленка'], 'пленка': ['стекло'],
    'крышка': ['корпус'], 'корпус': ['крышка'], 'камера': ['камеры'],
    'шлейф': ['flex'], 'инструмент': ['отвертка', 'пинцет', 'паяльная'],
}


def list_products():
    """Возвращает только опубликованные товары с данными для карточек."""
    return Product.objects.filter(active=True).select_related('category').prefetch_related('photos', 'specifications')


def serialize_product(product):
    """Формирует публичные поля, не включая внутренние операции магазина."""
    return {
        'id': product.pk, 'slug': product.slug, 'name': product.name, 'subtitle': product.subtitle,
        'description': product.description, 'part': product.part, 'category': product.category.slug,
        'brand': product.brand, 'device': product.device, 'compat': product.compatibility.splitlines(),
        'price': product.price, 'oldPrice': product.old_price, 'stock': product.stock,
        'warranty': product.warranty, 'badge': product.badge, 'featured': product.featured,
        'images': [photo.image.url for photo in product.photos.all()],
        'specs': {spec.name: spec.value for spec in product.specifications.all()},
    }


def normalize_expression(expression):
    """Приводит поля к тому же регистру и разделителям, что поисковый запрос."""
    # TRANSLATE сохраняет поиск по кириллице даже в базе с локалью C.
    expression = Func(expression, Value('ABCDEFGHIJKLMNOPQRSTUVWXYZАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯё'),
                      Value('abcdefghijklmnopqrstuvwxyzабвгдеежзийклмнопрстуфхцчшщъыьэюяе'),
                      function='TRANSLATE', output_field=TextField())
    for character in '-_/.,\n\r\t\u2011\u2013':
        expression = Replace(expression, Value(character), Value(' '), output_field=TextField())
    return expression


def search_products(parameters):
    """Фильтрует и ранжирует выборку в базе, не выгружая каталог в браузер."""
    products = list_products()
    for parameter, field in [('cat', 'category__slug'), ('brand', 'brand')]:
        values = [value for value in parameters.get(parameter, '').split(',') if value][:50]
        if values:
            products = products.filter(**{f'{field}__in': values})
    if parameters.get('stock') == '1':
        products = products.filter(stock__gt=0)
    minimum, maximum = parameters.get('min', ''), parameters.get('max', '')
    if minimum.isdecimal() and maximum.isdecimal() and int(minimum) > int(maximum):
        minimum, maximum = maximum, minimum
    for value, lookup in [(minimum, 'price__gte'), (maximum, 'price__lte')]:
        if value.isdecimal():
            products = products.filter(**{lookup: min(int(value), 2_147_483_647)})
    model = parameters.get('model', '')[:150]
    if model:
        products = products.filter(compatibility__regex=rf'(^|\r?\n){re.escape(model)}(\r?\n|$)')
    tokens = re.sub(r'[^a-zа-я0-9]+', ' ', parameters.get('q', '')[:200].lower().replace('ё', 'е')).split()[:12]
    if tokens:
        fields = {'part': ('part', 14), 'name': ('name', 9), 'device': ('device', 7),
                  'compatibility': ('compatibility', 7), 'brand': ('brand', 4),
                  'category': ('category__name', 2), 'subtitle': ('subtitle', 2)}
        annotations = {f'search_{key}': normalize_expression(F(field)) for key, (field, _) in fields.items()}
        annotations['search_compact'] = Replace(normalize_expression(Concat(
            'part', Value(' '), 'name', Value(' '), 'device', Value(' '), 'compatibility', output_field=TextField(),
        )), Value(' '), Value(''), output_field=TextField())
        products = products.annotate(**annotations)
        total = Value(0)
        for index, token in enumerate(tokens):
            cases = []
            for variant in [token, *SYNONYMS.get(token, [])]:
                cases.extend(Case(When(**{f'search_{key}__contains': variant}, then=Value(weight)),
                                  default=Value(0), output_field=IntegerField()) for key, (_, weight) in fields.items())
                cases.append(Case(When(search_compact__contains=variant, then=Value(6)), default=Value(0), output_field=IntegerField()))
            alias = f'token_score_{index}'
            products = products.annotate(**{alias: Greatest(*cases)}).filter(**{f'{alias}__gt': 0})
            total = total + F(alias)
        products = products.annotate(search_score=total)
    ordering = {'price-asc': ['price', 'id'], 'price-desc': ['-price', 'id'], 'stock': ['-stock', 'id']}
    return products.order_by(*ordering.get(parameters.get('sort'), ['-search_score', 'id'] if tokens else ['id']))


def get_facets():
    """Считает категории и бренды без загрузки карточек товаров."""
    products = Product.objects.filter(active=True)
    return {
        'total': products.count(),
        'categories': dict(products.values('category__slug').annotate(total=Count('id')).values_list('category__slug', 'total')),
        'brands': dict(products.values('brand').annotate(total=Count('id')).values_list('brand', 'total')),
        'modelBrands': list(products.exclude(category__slug='tools').order_by('brand').values_list('brand', flat=True).distinct()),
    }
