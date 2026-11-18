"""Ограничивает внутренние экраны на машине с демонстрационной базой."""
from ipaddress import ip_address, ip_network

from django.conf import settings
from django.http import HttpResponseNotFound


def restrict_local_staff(get_response):
    """Разрешает служебные пути с этого компьютера и из указанных подсетей."""
    networks = tuple(ip_network(value.strip()) for value in settings.SHOP_STAFF_NETWORKS if value.strip())

    def check_request(request):
        section = request.path_info.lstrip('/').split('/', 1)[0]
        if section in ('admin', 'warehouse'):
            try:
                address = ip_address(request.META.get('REMOTE_ADDR', ''))
            except ValueError:
                return HttpResponseNotFound()
            if not (address.is_loopback or any(address in network for network in networks)):
                return HttpResponseNotFound()
        return get_response(request)

    return check_request
