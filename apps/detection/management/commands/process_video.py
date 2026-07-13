"""Commande de management : traite un fichier vidéo pour une caméra et
persiste les détections résultantes (Phase 2 — pipeline offline)."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from apps.cameras.models import Camera
from apps.detection.services import run_pipeline_for_camera


class Command(BaseCommand):
    help = "Traite un fichier vidéo pour une caméra donnée et enregistre les VehicleDetection."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--camera", required=True, help="Nom exact de la caméra.")
        parser.add_argument("--video", required=True, help="Chemin du fichier vidéo à traiter.")
        parser.add_argument(
            "--recorded-at",
            default=None,
            help="Horodatage ISO 8601 du début de l'enregistrement (défaut : maintenant).",
        )

    def handle(self, *args, **options) -> None:
        try:
            camera = Camera.objects.get(name=options["camera"])
        except Camera.DoesNotExist as exc:
            raise CommandError(f"Caméra introuvable : « {options['camera']} ».") from exc

        video_path = Path(options["video"])
        if not video_path.exists():
            raise CommandError(f"Fichier vidéo introuvable : {video_path}")

        recorded_at = None
        if options["recorded_at"]:
            recorded_at = parse_datetime(options["recorded_at"])
            if recorded_at is None:
                raise CommandError(f"Horodatage invalide : {options['recorded_at']}")

        try:
            detections = run_pipeline_for_camera(camera, video_path, recorded_at=recorded_at)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(detections)} détection(s) enregistrée(s) pour « {camera.name} »."
            )
        )
