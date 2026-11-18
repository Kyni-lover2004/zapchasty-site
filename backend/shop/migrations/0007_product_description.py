from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shop', '0006_lower_board_cards')]
    operations = [
        migrations.AddField(
            model_name='product',
            name='description',
            field=models.TextField(
                'Описание', blank=True,
                help_text='Обычный текст. Если оставить поле пустым, сайт покажет базовое описание детали.',
            ),
        ),
    ]
