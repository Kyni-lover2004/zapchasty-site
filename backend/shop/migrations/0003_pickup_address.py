from django.db import migrations, models


PREVIOUS_ADDRESS = 'Рязань, ул. Почтовая, 62'
TEMPORARY_ADDRESS = 'Рязань, ул. Татарская, 24 (предварительно)'


def set_pickup_address(apps, schema_editor):
    """Заменяет прежний демонстрационный адрес."""
    settings = apps.get_model('shop', 'StoreSettings')
    settings.objects.using(schema_editor.connection.alias).filter(address=PREVIOUS_ADDRESS).update(address=TEMPORARY_ADDRESS)


def restore_pickup_address(apps, schema_editor):
    """Восстанавливает адрес при откате миграции."""
    settings = apps.get_model('shop', 'StoreSettings')
    settings.objects.using(schema_editor.connection.alias).filter(address=TEMPORARY_ADDRESS).update(address=PREVIOUS_ADDRESS)


class Migration(migrations.Migration):
    dependencies = [('shop', '0002_storesettings')]
    operations = [
        migrations.AlterField(
            model_name='storesettings',
            name='address',
            field=models.CharField('Адрес самовывоза', max_length=250, default=TEMPORARY_ADDRESS),
        ),
        migrations.RunPython(set_pickup_address, restore_pickup_address),
    ]
