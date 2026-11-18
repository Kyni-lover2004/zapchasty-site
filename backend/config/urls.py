from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from shop.views import get_catalog, get_home

urlpatterns = [
    path('', get_home), path('admin/', admin.site.urls),
    path('warehouse/', include('shop.warehouse')), path('api/catalog/', get_catalog),
]
if settings.DEBUG:
    urlpatterns += [re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'assets'})]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
