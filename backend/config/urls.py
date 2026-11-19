from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from shop.views import get_catalog, get_home, get_product_page, get_sitemap, get_robots, get_health

urlpatterns = [
    path('', get_home), path('admin/', admin.site.urls),
    path('warehouse/', include('shop.warehouse')), path('api/catalog/', get_catalog),
    path('product/<slug:slug>/', get_product_page, name='public_product'),
    path('sitemap.xml', get_sitemap), path('robots.txt', get_robots), path('health/', get_health),
]
if settings.DEBUG:
    urlpatterns += [re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'assets'})]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
