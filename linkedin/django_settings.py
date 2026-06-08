# linkedin/django_settings.py
"""
Minimal Django settings for using DjangoCRM's ORM + admin.
"""
import os
import sys
from pathlib import Path

# Playwright's sync API runs inside an async event loop, which triggers
# Django's async-safety check. We only use the ORM synchronously, so this is safe.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

ROOT_DIR = Path(__file__).resolve().parent.parent

BASE_DIR = ROOT_DIR

# Dev defaults; override via environment for real self-hosting.
SECRET_KEY = os.environ.get(
    "OPENOUTREACH_SECRET_KEY", "openoutreach-local-dev-key-change-in-production",
)

DEBUG = os.environ.get("OPENOUTREACH_DEBUG", "true").lower() != "false"

ALLOWED_HOSTS = os.environ.get("OPENOUTREACH_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.sites",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "crm.apps.CrmConfig",
    "chat.apps.ChatConfig",
    "linkedin",
    "controlcenter",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "linkedin.urls"

# Built single-page-app bundle (Vite output). The control center SPA's
# index.html is loaded as a Django template; its hashed assets live in
# ``frontend/dist/assets`` and are served via staticfiles.
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIST],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(ROOT_DIR / "data" / "db.sqlite3"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SITE_ID = 1

STATIC_URL = "/static/"
STATIC_ROOT = ROOT_DIR / "staticfiles"
# Serve the SPA's hashed bundle (frontend/dist/assets/*) under /static/.
STATICFILES_DIRS = [d for d in [FRONTEND_DIST] if d.exists()]

MEDIA_URL = "/media/"
MEDIA_ROOT = ROOT_DIR / "media"

# Control center SPA login route (the API returns 401/403; the SPA redirects).
LOGIN_URL = "/login"

DEFAULT_FROM_EMAIL = "noreply@localhost"
EMAIL_SUBJECT_PREFIX = "CRM: "

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

TESTING = sys.argv[1:2] == ["test"]
