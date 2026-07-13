"""Consumer WebSocket du dashboard temps réel (Phase 4). Un agent connecté
reçoit chaque nouvelle infraction dès sa détection, poussée par
apps.dashboard.services.broadcast_new_infraction via le group_send Channels
"infractions" — jamais de polling côté dashboard."""

from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer

INFRACTIONS_GROUP = "infractions"


class InfractionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        if not self.scope["user"].is_authenticated:
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(INFRACTIONS_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(INFRACTIONS_GROUP, self.channel_name)

    async def infraction_created(self, event: dict) -> None:
        """Handler du type d'événement "infraction.created" envoyé par
        group_send — Channels traduit les points en underscores pour
        résoudre le nom de la méthode."""
        await self.send_json(event["infraction"])
