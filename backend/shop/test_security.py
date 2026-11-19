"""Регрессии сетевого доступа, доверия прокси и лимита входа."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from .middleware import limit_staff_login, restrict_local_staff
from .models import LoginAttemptWindow


@override_settings(DEBUG=False, SHOP_BEHIND_PROXY=False, SHOP_STAFF_NETWORKS=[])
class StaffAccessTests(SimpleTestCase):
    def get_response(self, path, address, **headers):
        """Проверяет ограничение до обращения к представлению и базе."""
        request = RequestFactory().get(path, REMOTE_ADDR=address, **headers)
        return restrict_local_staff(lambda request: HttpResponse('allowed'))(request)

    def test_public_catalog_and_hidden_staff_paths(self):
        """Внешний посетитель видит витрину, но не служебные пути."""
        self.assertEqual(self.get_response('/api/catalog/', '203.0.113.5').status_code, 200)
        for path in ['/admin', '/admin/', '/admin/login/', '/warehouse', '/warehouse/stock/']:
            with self.subTest(path=path):
                self.assertEqual(self.get_response(path, '203.0.113.5').status_code, 404)

    def test_lan_and_spoofed_headers_do_not_grant_access(self):
        """Заголовки клиента и принадлежность домашней сети не дают доступ."""
        for address in ['192.168.1.25', '203.0.113.5']:
            self.assertEqual(self.get_response('/admin/', address,
                HTTP_X_REAL_IP='127.0.0.1', HTTP_X_FORWARDED_FOR='127.0.0.1').status_code, 404)

    def test_loopback_access(self):
        """Локальная работа остаётся доступной по IPv4 и IPv6."""
        for address in ['127.0.0.1', '::1']:
            self.assertEqual(self.get_response('/admin/', address).status_code, 200)

    @override_settings(SHOP_STAFF_NETWORKS=['10.8.0.5/32'])
    def test_explicit_staff_address(self):
        """Разрешается конкретный VPN-адрес, но не соседний компьютер."""
        self.assertEqual(self.get_response('/warehouse/', '10.8.0.5').status_code, 200)
        self.assertEqual(self.get_response('/warehouse/', '10.8.0.6').status_code, 404)

    @override_settings(SHOP_BEHIND_PROXY=True, SHOP_TRUSTED_PROXY_NETWORKS=['127.0.0.1/32'])
    def test_proxy_uses_real_client_and_fails_closed(self):
        """Прокси не превращает внешнего посетителя в локального."""
        self.assertEqual(self.get_response('/admin/', '127.0.0.1', HTTP_X_REAL_IP='203.0.113.5').status_code, 404)
        self.assertEqual(self.get_response('/api/catalog/', '127.0.0.1', HTTP_X_REAL_IP='203.0.113.5').status_code, 200)
        self.assertEqual(self.get_response('/admin/', '127.0.0.1', HTTP_X_REAL_IP='127.0.0.1').status_code, 200)
        for headers in [{}, {'HTTP_X_REAL_IP': 'invalid'}, {'HTTP_X_REAL_IP': '127.0.0.1,203.0.113.5'}]:
            self.assertEqual(self.get_response('/admin/', '127.0.0.1', **headers).status_code, 404)
        self.assertEqual(self.get_response('/admin/', '203.0.113.5', HTTP_X_REAL_IP='127.0.0.1').status_code, 404)

    @override_settings(DEBUG=True, SHOP_STAFF_NETWORKS=['192.168.1.0/24'])
    def test_debug_is_never_exposed_to_lan(self):
        """Даже разрешённая подсеть не получает отладочные страницы."""
        self.assertEqual(self.get_response('/', '192.168.1.25').status_code, 404)
        self.assertEqual(self.get_response('/', '127.0.0.1').status_code, 200)

    def test_invalid_peer_is_denied(self):
        """Отсутствующий или неверный адрес не открывает доступ."""
        for address in ['', 'invalid']:
            self.assertEqual(self.get_response('/admin/', address).status_code, 404)


@override_settings(SHOP_BEHIND_PROXY=False, SHOP_LOGIN_LIMIT=5, SHOP_LOGIN_WINDOW_SECONDS=300)
class LoginLimitTests(TestCase):
    def post_login(self, address='127.0.0.1', **headers):
        """Создаёт новый экземпляр middleware, как при другом процессе сервера."""
        request = RequestFactory().post('/admin/login/', REMOTE_ADDR=address, **headers)
        return limit_staff_login(lambda request: HttpResponse('login'))(request)

    def test_limit_is_shared_between_instances_and_cannot_be_spoofed(self):
        """Шестой запрос блокируется, смена заголовков не сбрасывает лимит."""
        for attempt in range(5):
            self.assertEqual(self.post_login(HTTP_X_FORWARDED_FOR=f'203.0.113.{attempt}').status_code, 200)
        response = self.post_login(HTTP_X_REAL_IP='203.0.113.99')
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(LoginAttemptWindow.objects.get().attempts, 5)

    def test_window_expires_and_addresses_are_independent(self):
        """Истечение срока снимает ограничение только соответствующего окна."""
        for _ in range(5):
            self.post_login()
        self.assertEqual(self.post_login(address='::1').status_code, 200)
        LoginAttemptWindow.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post_login().status_code, 200)
        self.assertEqual(LoginAttemptWindow.objects.get().attempts, 1)

    def test_get_does_not_consume_limit(self):
        """Открытие страницы входа не расходует попытки."""
        request = RequestFactory().get('/admin/login/')
        self.assertEqual(limit_staff_login(lambda request: HttpResponse())(request).status_code, 200)
        self.assertFalse(LoginAttemptWindow.objects.exists())

    @override_settings(SHOP_BEHIND_PROXY=True, SHOP_TRUSTED_PROXY_NETWORKS=['127.0.0.1/32'])
    def test_proxy_limit_tracks_real_address(self):
        """Разные клиенты прокси получают отдельные окна."""
        for _ in range(5):
            self.post_login(HTTP_X_REAL_IP='10.8.0.5')
        self.assertEqual(self.post_login(HTTP_X_REAL_IP='10.8.0.5').status_code, 429)
        self.assertEqual(self.post_login(HTTP_X_REAL_IP='10.8.0.6').status_code, 200)

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True, SHOP_STAFF_NETWORKS=[])
    def test_hidden_login_cannot_consume_limit_or_redirect(self):
        """Полная цепочка отвечает 404 внешнему клиенту ещё до HTTPS-редиректа."""
        response = self.client.post('/admin/login/', REMOTE_ADDR='203.0.113.5')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(LoginAttemptWindow.objects.exists())

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_csrf_and_authentication_remain_required(self):
        """Лимитер не заменяет CSRF и проверку авторизации Django."""
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/admin/login/', {}).status_code, 403)
        self.assertEqual(client.get('/admin/shop/product/').status_code, 302)
        self.assertEqual(client.get('/warehouse/stock/').status_code, 302)


@override_settings(SHOP_BEHIND_PROXY=False, SHOP_LOGIN_LIMIT=5, SHOP_LOGIN_WINDOW_SECONDS=300)
class ConcurrentLoginTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_parallel_requests_cannot_exceed_limit(self):
        """Одновременные запросы с разными соединениями делят одно окно."""
        def post_login(attempt):
            """Имитирует отдельный процесс с собственным соединением к базе."""
            close_old_connections()
            try:
                request = RequestFactory().post('/admin/login/', REMOTE_ADDR='127.0.0.1')
                return limit_staff_login(lambda request: HttpResponse())(request).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=10) as executor:
            statuses = list(executor.map(post_login, range(10)))
        self.assertEqual(statuses.count(200), 5)
        self.assertEqual(statuses.count(429), 5)
        self.assertEqual(LoginAttemptWindow.objects.get().attempts, 5)
