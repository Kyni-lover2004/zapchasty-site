"""Публичное чтение каталога; запись доступна только через админку."""
import json
import re
from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from .models import Product, Category, StoreSettings

@require_GET
@never_cache
def get_catalog(request):
    """Отдаёт опубликованные товары с фотографиями и характеристиками."""
    seed = json.loads((settings.BASE_DIR / 'backend/shop/seed.json').read_text())
    products = []
    for product in Product.objects.filter(active=True).select_related('category').prefetch_related('photos', 'specifications'):
        products.append({
            'id': product.pk, 'slug': product.slug, 'name': product.name, 'subtitle': product.subtitle,
            'description': product.description,
            'part': product.part, 'category': product.category.slug, 'brand': product.brand,
            'device': product.device, 'compat': product.compatibility.splitlines(),
            'price': product.price, 'oldPrice': product.old_price, 'stock': product.stock,
            'warranty': product.warranty, 'badge': product.badge, 'featured': product.featured,
            'images': [photo.image.url for photo in product.photos.all()],
            'specs': {spec.name: spec.value for spec in product.specifications.all()},
        })
    store = StoreSettings.objects.get(pk=1)
    seed['CONTACTS'].update(
        addressFull=store.address, hours=store.hours, phone=store.phone,
        phoneHref=re.sub(r'[^+0-9]', '', store.phone),
    )
    seed['SOCIAL_LINKS'] = {'telegram': store.telegram, 'vk': store.vk}
    seed['PRODUCTS'] = products
    seed['CATEGORIES'] = [{'id': category.slug, 'name': category.name, 'icon': category.icon, 'desc': category.description} for category in Category.objects.all()]
    return JsonResponse(seed)

@require_GET
def get_home(request):
    """Отдаёт витрину без доступа к служебным файлам проекта."""
    return FileResponse((settings.BASE_DIR / 'index.html').open('rb'), content_type='text/html')
