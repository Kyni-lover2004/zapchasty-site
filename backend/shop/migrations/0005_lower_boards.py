from django.db import migrations


def separate_lower_boards(apps, schema_editor):
    """Создаёт раздел нижних плат и переносит штатные сборки с платой."""
    db = schema_editor.connection.alias
    categories = apps.get_model('shop', 'Category').objects.using(db)
    products = apps.get_model('shop', 'Product').objects.using(db)
    lower_boards, _ = categories.get_or_create(
        slug='lower-boards',
        defaults={
            'name': 'Нижние платы',
            'icon': 'charging',
            'description': 'Нижние платы смартфонов, в том числе с разъёмом зарядки',
        },
    )
    categories.filter(slug='charging', description='Разъёмы зарядки, шлейфы и нижние платы').update(
        description='Разъёмы зарядки для смартфонов',
    )
    products.filter(
        category__slug='charging',
        slug__in=['razem-redmi-note-12', 'razem-galaxy-a54'],
        specifications__name='Тип',
        specifications__value='С нижней платой',
    ).update(category=lower_boards)


class Migration(migrations.Migration):
    dependencies = [('shop', '0004_teardown_categories')]
    operations = [migrations.RunPython(separate_lower_boards, migrations.RunPython.noop)]
