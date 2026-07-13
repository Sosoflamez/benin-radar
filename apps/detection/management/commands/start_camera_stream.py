"""Commande de management : lance l'ingestion continue d'une caméra en tâche
de fond Celery (Phase 4 — flux RTSP, contrairement à process_video qui
traite un fichier fini de façon synchrone)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.cameras.models import Camera
from apps.detection.tasks import run_camera_stream


class Command(BaseCommand):
    help = "Démarre l'ingestion continue d'une caméra (tâche Celery de fond)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--camera", required=True, help="Nom exact de la caméra.")

    def handle(self, *args, **options) -> None:
        try:
            camera = Camera.objects.get(name=options["camera"])
        except Camera.DoesNotExist as exc:
            raise CommandError(f"Caméra introuvable : « {options['camera']} ».") from exc

        if not camera.is_active:
            raise CommandError(f"La caméra « {camera.name} » est inactive.")

        result = run_camera_stream.delay(camera.id)
        self.stdout.write(
            self.style.SUCCESS(
                f"Ingestion lancée pour « {camera.name} » (tâche Celery {result.id})."
            )
        )
