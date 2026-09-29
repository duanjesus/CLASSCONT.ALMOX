"""Configurações do Django para o CLASSCONT.ALMOX.

Tudo que muda entre ambientes vem de variáveis de ambiente (12-factor).
Os valores padrão servem para o ambiente de desenvolvimento do docker compose.
"""

import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import django_stubs_ext

# Permite anotar genéricos do Django em tempo de execução (ex.: ModelAdmin[Setor], ListView[Material])
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome: str, padrao: str = "") -> str:
    return os.environ.get(nome, padrao)


def env_bool(nome: str, padrao: bool = False) -> bool:
    return env(nome, "1" if padrao else "0").lower() in {"1", "true", "sim", "yes"}


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-inseguro-troque-em-producao-classcont-almox")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,backend").split(",")
CSRF_TRUSTED_ORIGINS = [
    o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8082").split(",") if o
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Necessário para o FORM_RENDERER TemplatesSetting achar os templates padrão de formulário
    "django.forms",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "contas",
    "estoque",
    "requisicoes",
    "api",
    "painel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "painel.middleware.ErrosDeDominioMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "painel.context_processors.painel",
            ],
        },
    },
]

# Renderer próprio: define o layout de <form> e de cada campo (equivalente ao "form theme" do Twig)
FORM_RENDERER = "painel.formularios.RendererPainel"

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "almox"),
        "USER": env("POSTGRES_USER", "almox"),
        "PASSWORD": env("POSTGRES_PASSWORD", "almox"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5434"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_USER_MODEL = "contas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "painel:login"
LOGIN_REDIRECT_URL = "painel:dashboard"
LOGOUT_REDIRECT_URL = "painel:login"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cache usado pelo limitador de tentativas de login. Em produção com vários
# processos, troque por Redis (django.core.cache.backends.redis.RedisCache).
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- E-mail (Mailpit em desenvolvimento) ---
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
DEFAULT_FROM_EMAIL = "Almoxarifado CLASSCONT <almoxarifado@classcont.local>"

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "api.excecoes.tratar_excecao",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CLASSCONT.ALMOX API",
    "DESCRIPTION": "Requisições de material, aprovações e consumo por setor.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Regras do sistema ---
ALMOX: dict[str, Any] = {
    # Tentativas de login erradas por e-mail+IP antes do bloqueio temporário
    "LOGIN_MAX_TENTATIVAS": 5,
    "LOGIN_JANELA_SEGUNDOS": 60,
    # Endereço do front React (usado nos links dos e-mails)
    "URL_FRONT": env("ALMOX_URL_FRONT", "http://localhost:5174"),
    "URL_PAINEL": env("ALMOX_URL_PAINEL", "http://localhost:8082"),
}

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
