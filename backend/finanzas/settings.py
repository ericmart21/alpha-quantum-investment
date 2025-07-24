#backend/finanzas/settings.py
from pathlib import Path
import os


TWELVE_DATA_API_KEY = "7845cebeb98c4b519a6ce293374a2389"
# backend/finanzas/settings.py

FINNHUB_API_KEY = 'd1vp4b1r01qmbi8pd5e0d1vp4b1r01qmbi8pd5eg'

ALPHA_VANTAGE_API_KEY= 'F4KQD1B0TP6MEXN3'


# BASE_DIR apunta a la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# CLAVE SECRETA PARA DESARROLLO
SECRET_KEY = 'django-insecure-edn&(%&uzd&jwedj9nsphswee#o!%!x%^&l7%y(#gn(=vxvv#k'

# NO USAR DEBUG EN PRODUCCIÓN
DEBUG = True

# PERMITIR TODO EN DESARROLLO
ALLOWED_HOSTS = ['*']


# APLICACIONES INSTALADAS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "corsheaders",
    'rest_framework',
    'alpha_quantum',
    'widget_tweaks',
    'cronjobs',
]


# MIDDLEWARE
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# URLS PRINCIPALES
ROOT_URLCONF = 'finanzas.urls'


# CONFIGURACIÓN DE TEMPLATES
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# PUNTO DE ENTRADA WSGI
WSGI_APPLICATION = 'finanzas.wsgi.application'


# BASE DE DATOS
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'alpha_quantum.CustomUser'

# VALIDACIÓN DE CONTRASEÑAS
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# CONFIGURACIÓN DE LOCALIZACIÓN
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = 'index'
LOGOUT_REDIRECT_URL = 'login'

# ARCHIVOS ESTÁTICOS (CSS, JS, imágenes)
STATIC_URL = 'static/'

# STATICFILES_DIRS = [
#     BASE_DIR / 'static',
# ]

# ARCHIVOS SUBIDOS POR USUARIOS (opcional si usas imágenes o archivos)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# TIPO DE CLAVE PRIMARIA POR DEFECTO
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True  # Solo para desarrollo