import os
from pathlib import Path

from app.config import settings as rag_settings

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-local-dev-key")
DEBUG = bool(rag_settings.DEBUG)
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django_app",
    "channels",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django_backend.middleware.CorsAllowAllMiddleware",
]

ROOT_URLCONF = "django_backend.urls"
WSGI_APPLICATION = "django_backend.wsgi.application"
ASGI_APPLICATION = "django_backend.asgi.application"

# Channels configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
        # For production with Redis:
        # "BACKEND": "channels_redis.core.RedisChannelLayer",
        # "CONFIG": {
        #     "hosts": [("127.0.0.1", 6379)],
        # },
    },
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "django_app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
            ],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "django_app" / "static" / "frontend",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = str(Path(rag_settings.DOCUMENTS_PATH).resolve().parent)
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Frontend hits endpoints without trailing slash, e.g. /api/upload
APPEND_SLASH = False

# Logging
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} | {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "llm_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "llm.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 3,
            "formatter": "verbose",
        },
        "general_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "django.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "llm": {
            "handlers": ["console", "llm_file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django": {
            "handlers": ["console", "general_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
