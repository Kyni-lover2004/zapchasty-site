from django.db import migrations, models


def update_lower_board_cards(apps, schema_editor):
    """Отличает существующие карточки плат от отдельных разъёмов."""
    db = schema_editor.connection.alias
    categories = apps.get_model('shop', 'Category').objects.using(db)
    products = apps.get_model('shop', 'Product').objects.using(db)
    specifications = apps.get_model('shop', 'Specification').objects.using(db)

    categories.filter(slug='lower-boards', icon='charging').update(icon='lower-board')
    for slug, device in [
        ('razem-redmi-note-12', 'Redmi Note 12'),
        ('razem-galaxy-a54', 'Galaxy A54'),
    ]:
        product = products.filter(
            category__slug='lower-boards', slug=slug, name=f'Разъём зарядки для {device}',
        ).first()
        if product is None:
            continue
        product.name = f'Нижняя плата для {device}'
        fields = ['name']
        if product.subtitle == 'USB-C, с платой':
            product.subtitle = 'Плата в сборе с USB-C'
            fields.append('subtitle')
        product.save(using=db, update_fields=fields)
        specs = specifications.filter(product=product)
        specs.filter(name='Тип', value='С нижней платой').update(value='Нижняя плата')
        specs.filter(name='Комплектация', value='Плата, шлейф').update(value='Нижняя плата в сборе')


class Migration(migrations.Migration):
    dependencies = [('shop', '0005_lower_boards')]
    operations = [
        migrations.AlterField(
            model_name='category',
            name='icon',
            field=models.CharField(
                'Иконка', max_length=20, default='tool',
                choices=[
                    ('display', 'display'), ('battery', 'battery'), ('flex', 'flex'),
                    ('camera', 'camera'), ('glass', 'glass'), ('back', 'back'),
                    ('charging', 'charging'), ('lower-board', 'lower-board'), ('tool', 'tool'),
                ],
            ),
        ),
        migrations.RunPython(update_lower_board_cards, migrations.RunPython.noop),
    ]
