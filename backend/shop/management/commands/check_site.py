"""Проверка доступности с журналом переходов и необязательным уведомлением владельца."""
import json
import logging
import os
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger('shop.monitor')


def check_availability(url):
    """Ожидает успешный ответ проверки базы за десять секунд."""
    try:
        with urlopen(url, timeout=10) as response:
            data = json.loads(response.read(4096))
            return response.status == 200 and isinstance(data, dict) and data.get('status') == 'ok'
    except (OSError, URLError, ValueError):
        return False


def send_alert(available):
    """Отправляет только служебный статус; данные покупателей не используются."""
    message = 'PartStack: сайт снова доступен.' if available else 'PartStack: сайт недоступен. Проверьте сервер и базу данных.'
    if not settings.SHOP_ALERTS_ENABLED:
        return
    if not settings.SHOP_TELEGRAM_TOKEN or not settings.SHOP_TELEGRAM_CHAT_ID:
        raise CommandError('Для уведомлений нужны SHOP_TELEGRAM_TOKEN и SHOP_TELEGRAM_CHAT_ID.')
    request = Request('https://api.telegram.org/bot' + settings.SHOP_TELEGRAM_TOKEN + '/sendMessage',
                      data=urlencode({'chat_id': settings.SHOP_TELEGRAM_CHAT_ID, 'text': message}).encode(), method='POST')
    try:
        with urlopen(request, timeout=10) as response:
            if not json.loads(response.read(4096)).get('ok'):
                raise CommandError('Telegram не подтвердил отправку уведомления.')
    except (OSError, URLError, ValueError):
        raise CommandError('Не удалось отправить служебное уведомление в Telegram.') from None


class Command(BaseCommand):
    help = 'Проверяет доступность магазина и пишет в журнал только изменение статуса.'

    def add_arguments(self, parser):
        """Позволяет проверять тестовый адрес и хранить отдельное состояние."""
        parser.add_argument('--url', default=settings.SHOP_MONITOR_URL)
        parser.add_argument('--state-file', default=settings.SHOP_MONITOR_STATE)

    def handle(self, *args, **options):
        """Сохраняет статус после успешного уведомления, чтобы повторить сбой отправки."""
        available = check_availability(options['url'])
        path = Path(options['state_file'])
        try:
            previous = json.loads(path.read_text()).get('available')
        except FileNotFoundError:
            previous = None
        except (OSError, ValueError) as error:
            raise CommandError('Не удалось прочитать состояние мониторинга.') from error
        if previous != available:
            logger.log(logging.INFO if available else logging.ERROR, 'Магазин %s.', 'доступен' if available else 'недоступен')
            if previous is not None or not available:
                send_alert(available)
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as output:
                json.dump({'available': available}, output)
                temporary_path = output.name
            os.replace(temporary_path, path)
        if not available:
            raise CommandError('Проверка доступности не пройдена.')
