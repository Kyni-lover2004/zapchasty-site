"""Публичное чтение каталога; запись доступна только через админку."""
import json
import re
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db import connection, DatabaseError
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from xml.sax.saxutils import escape as escape_xml
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from .models import Product, Category, StoreSettings
from .catalog import get_facets, list_products, search_products, serialize_product

logger = logging.getLogger(__name__)

@require_GET
@never_cache
def get_catalog(request):
    """Отдаёт стартовую витрину или ограниченную выборку каталога."""
    mode = request.GET.get('mode', 'bootstrap')
    if mode == 'search':
        page = Paginator(search_products(request.GET), 24).get_page(request.GET.get('page'))
        return JsonResponse({'PRODUCTS': [serialize_product(product) for product in page],
                             'total': page.paginator.count, 'page': page.number, 'pages': page.paginator.num_pages})
    if mode == 'ids':
        values = request.GET.get('ids', '').split(',')
        if len(values) > 200 or any(value and (not value.isdecimal() or len(value) > 18) for value in values):
            return JsonResponse({'error': 'Некорректный список товаров.'}, status=400)
        products = list_products().filter(pk__in=[int(value) for value in values if value])
        return JsonResponse({'PRODUCTS': [serialize_product(product) for product in products]})
    if mode == 'product':
        product = get_object_or_404(list_products(), slug=request.GET.get('slug', '')[:250])
        return JsonResponse({'PRODUCTS': [serialize_product(product)]})
    if mode == 'models':
        counts = {}
        products = Product.objects.filter(active=True).exclude(category__slug='tools')
        allowed_models = None
        if request.GET.get('brand'):
            allowed_models = set()
            for compatibility in products.filter(brand=request.GET['brand'][:100]).values_list('compatibility', flat=True):
                allowed_models.update(compatibility.splitlines())
        query = request.GET.get('q', '')[:150].lower().replace('ё', 'е')
        for compatibility in products.values_list('compatibility', flat=True).iterator(chunk_size=200):
            for model in set(compatibility.splitlines()):
                if model and (allowed_models is None or model in allowed_models) and query in model.lower().replace('ё', 'е'):
                    counts[model] = counts.get(model, 0) + 1
        page = Paginator(sorted(counts), 60).get_page(request.GET.get('page'))
        return JsonResponse({'models': [{'name': name, 'count': counts[name]} for name in page],
                             'page': page.number, 'pages': page.paginator.num_pages, 'total': len(counts)})
    if mode != 'bootstrap':
        return JsonResponse({'error': 'Неизвестный режим каталога.'}, status=400)
    seed = json.loads((settings.BASE_DIR / 'backend/shop/seed.json').read_text())
    products = [serialize_product(product) for product in list_products().order_by('-featured', 'id')[:12]]
    store = StoreSettings.objects.get(pk=1)
    seed['CONTACTS'].update(
        addressFull=store.address, hours=store.hours, phone=store.phone,
        phoneHref=re.sub(r'[^+0-9]', '', store.phone),
    )
    seed['SOCIAL_LINKS'] = {'telegram': store.telegram, 'vk': store.vk}
    seed['PRODUCTS'] = products
    seed['FACETS'] = get_facets()
    seed['SERVER_CATALOG'] = True
    seed['CATEGORIES'] = [{'id': category.slug, 'name': category.name, 'icon': category.icon, 'desc': category.description} for category in Category.objects.all()]
    return JsonResponse(seed)

@require_GET
@never_cache
def get_home(request):
    """Отдаёт витрину без доступа к служебным файлам проекта."""
    return HttpResponse(render_store_page(request), content_type='text/html')


def render_store_page(request, product=None):
    """Добавляет в каркас безопасные метаданные и читаемую без JavaScript карточку."""
    html = (settings.BASE_DIR / 'index.html').read_text()
    title = f'{product.name} — {product.part} — PartStack' if product else 'PartStack — запчасти для ремонта телефонов в Рязани'
    description = (product.description or f'{product.name}. {product.subtitle}. Цена {product.price} ₽. Самовывоз в Рязани.')[:300] if product else 'Запчасти для ремонта телефонов в Рязани. Каталог, наличие и самовывоз.'
    path = reverse('public_product', args=[product.slug]) if product else '/'
    base = settings.SHOP_PUBLIC_URL.rstrip('/') or request.build_absolute_uri('/').rstrip('/')
    canonical = base + path
    image = product.photos.first() if product else None
    image_url = (base + image.image.url) if image else base + '/assets/img/partstack-share.jpg'
    metadata = render_to_string('shop/public_metadata.html', {'title': title, 'description': description,
        'canonical': canonical, 'image_url': image_url, 'product': product})
    html = re.sub(r'<title>.*?</title>', lambda match: '<title>' + str(escape(title)) + '</title>', html, count=1)
    html = re.sub(r'<meta name="description"[^>]*>', '', html, count=1)
    html = html.replace('</head>', metadata + '\n</head>')
    if product:
        fallback = render_to_string('shop/public_product.html', {'product': product})
        html = html.replace('<!-- public-fallback -->', fallback)
    return html


@require_GET
@never_cache
def get_product_page(request, slug):
    """Возвращает отдельный индексируемый адрес опубликованного товара."""
    product = get_object_or_404(list_products(), slug=slug)
    return HttpResponse(render_store_page(request, product))


@require_GET
def get_sitemap(request):
    """Перечисляет только публичные опубликованные страницы магазина."""
    base = settings.SHOP_PUBLIC_URL.rstrip('/') or request.build_absolute_uri('/').rstrip('/')
    paths = ['/'] + [reverse('public_product', args=[slug]) for slug in Product.objects.filter(active=True).values_list('slug', flat=True)]
    entries = ''.join(f'<url><loc>{escape_xml(base + path)}</loc></url>' for path in paths)
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + entries + '</urlset>', content_type='application/xml')


@require_GET
def get_robots(request):
    """Разрешает публичные карточки, исключая служебные разделы и API."""
    base = settings.SHOP_PUBLIC_URL.rstrip('/') or request.build_absolute_uri('/').rstrip('/')
    return HttpResponse(f'User-agent: *\nDisallow: /admin\nDisallow: /warehouse\nDisallow: /api/\nSitemap: {base}/sitemap.xml\n', content_type='text/plain')


@require_GET
@never_cache
def get_health(request):
    """Проверяет соединение с базой, не раскрывая причины сбоя посетителю."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok'})
    except DatabaseError:
        logger.error('Проверка доступности: база данных недоступна.')
        return JsonResponse({'status': 'unavailable'}, status=503)
