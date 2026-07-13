"""Réglages Django communs à tous les environnements."""

from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "simple_history",
    "apps.cameras",
    "apps.detection",
    "apps.anpr",
    "apps.infractions",
    "apps.dashboard",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Porto-Novo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "120/min",
    },
}

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# run_camera_stream tourne sans limite de temps (ingestion RTSP continue) :
# isolée sur sa propre queue pour ne pas faire attendre les tâches courtes
# (OCR ANPR, purge RGPD) derrière elle sur la concurrency prefork par défaut.
CELERY_TASK_ROUTES = {
    "apps.detection.tasks.run_camera_stream": {"queue": "streams"},
}
# Purge RGPD/APDP (Phase 5, sécurité) : chaque nuit à 3h, hors heures de
# pointe du dashboard.
CELERY_BEAT_SCHEDULE = {
    "purge-stale-detections": {
        "task": "apps.detection.tasks.purge_stale_detections",
        "schedule": crontab(hour=3, minute=0),
    },
}

# Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL")]},
    },
}

# Cache Redis (backend natif Django, paquet `redis` déjà en dépendance).
# Requis pour que le verrou d'ingestion par caméra (apps.detection.tasks)
# soit partagé entre tous les processus worker Celery — un LocMemCache par
# défaut ne l'est pas.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL"),
    },
}

# Règles métier Benin-radar
SPEED_TOLERANCE_KMH = env.int("SPEED_TOLERANCE_KMH", default=5)
DETECTION_RETENTION_DAYS = env.int("DETECTION_RETENTION_DAYS", default=7)

# Pipeline vision (Phase 2)
ML_MODELS_DIR = BASE_DIR / "ml_models"
YOLO_MODEL_WEIGHTS = env.str("YOLO_MODEL_WEIGHTS", default="yolov8n.pt")
PIPELINE_SAMPLE_FPS = env.int("PIPELINE_SAMPLE_FPS", default=15)
DETECTION_CONFIDENCE_THRESHOLD = env.float("DETECTION_CONFIDENCE_THRESHOLD", default=0.4)
TRACKING_CONFIDENCE_THRESHOLD = env.float("TRACKING_CONFIDENCE_THRESHOLD", default=0.5)
# Ingestion continue (Phase 4) : durée sans nouvelle détection avant de
# finaliser une piste. Doit rester strictement supérieure au délai
# d'abandon de piste de ByteTrack (30 / PIPELINE_SAMPLE_FPS secondes) —
# voir apps/detection/pipeline/types.py::PipelineConfig.__post_init__.
PIPELINE_TRACK_TIMEOUT_S = env.float("PIPELINE_TRACK_TIMEOUT_S", default=3.0)

# ANPR (Phase 3)
ANPR_EASYOCR_GPU = env.bool("ANPR_EASYOCR_GPU", default=False)
