"""
ASGI config for config project.

Le routage WebSocket (notifications d'infractions live) sera ajouté en Phase 4.
"""

import os

from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
    }
)
