from django.db import migrations


def add_teardown_categories(apps, schema_editor):
    """Добавляет разделы деталей, отмеченных на схеме разбора."""
    category = apps.get_model('shop', 'Category')
    catalog = category.objects.using(schema_editor.connection.alias)
    additions = [
        ('boards', 'Основные платы', 'flex', 'Системные платы смартфонов'),
        ('board-components', 'Компоненты плат', 'tool', 'Микросхемы, контроллеры и другие элементы для ремонта плат'),
        ('speakers', 'Динамики', 'charging', 'Разговорные и полифонические динамики смартфонов'),
    ]
    for slug, name, icon, description in additions:
        catalog.get_or_create(slug=slug, defaults={'name': name, 'icon': icon, 'description': description})


class Migration(migrations.Migration):
    dependencies = [('shop', '0003_pickup_address')]
    operations = [migrations.RunPython(add_teardown_categories, migrations.RunPython.noop)]
