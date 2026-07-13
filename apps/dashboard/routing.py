from django.urls import path

from apps.dashboard.consumers import InfractionConsumer

websocket_urlpatterns = [
    path("ws/infractions/", InfractionConsumer.as_asgi()),
]
