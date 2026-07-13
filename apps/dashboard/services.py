"""Notifications temps réel du dashboard (Phase 4). Appelé depuis
apps.infractions.services au moment de la création d'une Infraction — import
tardif à cet endroit pour la même raison que apps.anpr.tasks dans
apps.infractions.services (éviter un couplage direct entre apps métier)."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.dashboard.consumers import INFRACTIONS_GROUP
from apps.infractions.models import Infraction


def _serialize_infraction(infraction: Infraction) -> dict:
    return {
        "id": infraction.id,
        "camera_id": infraction.camera_id,
        "camera_name": infraction.camera.name,
        "recorded_speed_kmh": str(infraction.recorded_speed_kmh),
        "speed_limit_kmh": infraction.speed_limit_kmh,
        "status": infraction.status,
        "created_at": infraction.created_at.isoformat(),
    }


def broadcast_new_infraction(infraction: Infraction) -> None:
    """Pousse la nouvelle infraction à tous les agents connectés au
    dashboard. Best-effort : l'absence de channel layer (ex. tests sans
    Redis) ne doit jamais faire échouer la création de l'infraction."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        INFRACTIONS_GROUP,
        {"type": "infraction.created", "infraction": _serialize_infraction(infraction)},
    )
