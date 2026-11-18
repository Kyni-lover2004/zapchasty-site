"""Однократный перенос демонстрационного каталога в PostgreSQL."""
import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.core.management.color import no_style
from shop.models import Category, Product, Specification

class Command(BaseCommand):
    help = 'Перенести начальный каталог; существующие товары не перезаписываются.'

    @transaction.atomic
    def handle(self, *args, **options):
        """Создаёт исходные товары с прежними ID и адресами."""
        if Product.objects.exists():
            raise CommandError('База уже содержит товары. Импорт остановлен, данные не изменены.')
        data = json.loads((settings.BASE_DIR / 'backend/shop/seed.json').read_text())
        for category in data['CATEGORIES']:
            Category.objects.get_or_create(slug=category['id'], defaults={'name': category['name'], 'icon': category['icon'], 'description': category['desc']})
        for item in data['PRODUCTS']:
            product = Product.objects.create(id=item['id'], slug=item['slug'], name=item['name'], part=item['part'], subtitle=item['subtitle'], category=Category.objects.get(slug=item['category']), brand=item['brand'], device=item['device'], compatibility='\n'.join(item['compat']), price=item['price'], old_price=item.get('oldPrice'), stock=item['stock'], warranty=item['warranty'], badge=item.get('badge',''), featured=item.get('featured',False))
            for name, value in item['specs'].items():
                Specification.objects.create(product=product,name=name,value=value)
        with connection.cursor() as cursor:
            for statement in connection.ops.sequence_reset_sql(no_style(), [Product]):
                cursor.execute(statement)
        self.stdout.write(self.style.SUCCESS(f'Перенесено товаров: {Product.objects.count()}'))
