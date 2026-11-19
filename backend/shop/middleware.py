"""Закрывает служебные страницы и ограничивает попытки входа."""
from datetime import timedelta
from hashlib import sha256
from ipaddress import ip_address, ip_network

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseNotFound
from django.utils import timezone

from .models import LoginAttemptWindow


def get_client_address(request):
    """Принимает адрес клиента только от явно доверенного прокси."""
    try:
        address = ip_address(request.META.get('REMOTE_ADDR', ''))
        if settings.SHOP_BEHIND_PROXY:
            proxies = (ip_network(value.strip()) for value in settings.SHOP_TRUSTED_PROXY_NETWORKS if value.strip())
            if not any(address in network for network in proxies):
                return None
            address = ip_address(request.META.get('HTTP_X_REAL_IP', ''))
        return address
    except ValueError:
        return None


def restrict_local_staff(get_response):
    """Скрывает служебные пути; отладочный сервер доступен только локально."""
    networks = tuple(ip_network(value.strip()) for value in settings.SHOP_STAFF_NETWORKS if value.strip())

    def check_request(request):
        """Проверяет адрес до перенаправлений, авторизации и обработки форм."""
        address = get_client_address(request)
        if address is None or (settings.DEBUG and not address.is_loopback):
            return HttpResponseNotFound()
        section = request.path_info.lstrip('/').split('/', 1)[0]
        if section in ('admin', 'warehouse'):
            if not (address.is_loopback or any(address in network for network in networks)):
                return HttpResponseNotFound()
        return get_response(request)

    return check_request


def limit_staff_login(get_response):
    """Хранит общий для процессов лимит POST-запросов входа в базе."""
    def check_request(request):
        """Разрешает не более пяти отправок формы за пять минут с адреса."""
        if request.method == 'POST' and request.path_info.rstrip('/') == '/admin/login':
            address = get_client_address(request)
            if address is None:
                return HttpResponseNotFound()
            now = timezone.now()
            key = sha256(address.compressed.encode()).hexdigest()
            LoginAttemptWindow.objects.filter(expires_at__lte=now).delete()
            with transaction.atomic():
                window, _ = LoginAttemptWindow.objects.select_for_update().get_or_create(
                    key=key, defaults={'expires_at': now + timedelta(seconds=settings.SHOP_LOGIN_WINDOW_SECONDS)},
                )
                if window.attempts >= settings.SHOP_LOGIN_LIMIT:
                    response = HttpResponse('Слишком много попыток входа. Повторите позже.', status=429)
                    response['Retry-After'] = str(max(1, int((window.expires_at - now).total_seconds()) + 1))
                    response['Cache-Control'] = 'no-store'
                    return response
                window.attempts += 1
                window.save(update_fields=['attempts'])
        return get_response(request)

    return check_request
