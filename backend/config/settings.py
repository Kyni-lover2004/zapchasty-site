"""Настройки сервера; секреты и пути поступают из окружения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEBUG = os.environ.get('SHOP_DEBUG', '0') == '1'
SECRET_KEY = os.environ['SHOP_SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('SHOP_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
CSRF_TRUSTED_ORIGINS = list(filter(None, os.environ.get('SHOP_ORIGINS', '').split(',')))
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'shop.apps.ShopConfig']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
MIDDLEWARE.insert(0, 'shop.middleware.restrict_local_staff')
MIDDLEWARE.insert(1, 'shop.middleware.limit_staff_login')
SHOP_STAFF_NETWORKS = os.environ.get('SHOP_STAFF_NETWORKS', '').split(',')
SHOP_BEHIND_PROXY = os.environ.get('SHOP_BEHIND_PROXY', '0' if DEBUG else '1') == '1'
SHOP_TRUSTED_PROXY_NETWORKS = os.environ.get('SHOP_TRUSTED_PROXY_NETWORKS', '127.0.0.1/32,::1/128').split(',')
SHOP_LOGIN_LIMIT = 5
SHOP_LOGIN_WINDOW_SECONDS = 300
SHOP_PUBLIC_URL = os.environ.get('SHOP_PUBLIC_URL', '')
SHOP_MONITOR_URL = os.environ.get('SHOP_MONITOR_URL', 'http://127.0.0.1:8000/health/')
SHOP_MONITOR_STATE = os.environ.get('SHOP_MONITOR_STATE', str(BASE_DIR / '.local/monitor-state.json'))
SHOP_ALERTS_ENABLED = os.environ.get('SHOP_ALERTS_ENABLED', '0') == '1'
SHOP_TELEGRAM_TOKEN = os.environ.get('SHOP_TELEGRAM_TOKEN', '')
SHOP_TELEGRAM_CHAT_ID = os.environ.get('SHOP_TELEGRAM_CHAT_ID', '')
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'backend/templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ.get('PGDATABASE', 'z62'), 'USER': os.environ.get('PGUSER', 'z62'), 'PASSWORD': os.environ.get('PGPASSWORD', ''), 'HOST': os.environ.get('PGHOST', '127.0.0.1'), 'PORT': os.environ.get('PGPORT', '5432')}}
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'backend/static']
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('SHOP_MEDIA_ROOT', str(BASE_DIR / 'media')))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 28800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if SHOP_BEHIND_PROXY else None
SECURE_HSTS_SECONDS = 0 if DEBUG else 3600
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 20
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'standard': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'}},
    'loggers': {'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
                'shop': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}},
}
