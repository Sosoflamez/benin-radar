"""
ASGI config for config project.

Le routage WebSocket (notifications d'infractions live, Phase 4) est
authentifié via AuthMiddlewareStack : seul un agent avec une session Django
valide peut rejoindre le groupe "infractions" (voir
apps.dashboard.consumers.InfractionConsumer).
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

django_asgi_app = get_asgi_application()

# django_asgi_app doit être instancié avant l'import de apps.dashboard.routing
# pour que l'app registry Django soit prête quand les modèles y sont importés.
from apps.dashboard.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
