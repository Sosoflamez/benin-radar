"""Tâche Celery d'ingestion RTSP continue (Phase 4). Contrairement au
pipeline offline (apps.detection.services.run_pipeline_for_camera, fichier
fini), cette tâche tourne sans limite de temps tant que la caméra reste
active ; l'arrêt se fait en désactivant la caméra (Camera.is_active=False),
vérifié périodiquement plutôt qu'à chaque frame pour ne pas saturer la base.

Une coupure de flux (StreamConnectionError/StreamReadError) ne termine plus
la tâche : elle déclenche une reconnexion avec backoff exponentiel tant que
la caméra reste active (voir _run_with_reconnect). Isolation sur une queue
Celery dédiée : voir CELERY_TASK_ROUTES (config/settings/base.py)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from celery import shared_task
from django.conf import settings
from django.core.cache import cache

from apps.cameras.models import Camera
from apps.detection.pipeline.stream import StreamConnectionError, StreamReadError
from apps.detection.services import (
    purge_detections_without_infraction,
    run_live_pipeline_for_camera,
)

logger = logging.getLogger(__name__)

_LOCK_KEY_TEMPLATE = "detection:camera-stream-lock:{camera_id}"
# Délai de grâce initial : doit couvrir le chargement du modèle YOLO et la
# négociation RTSP avant que la première frame n'arrive et que le premier
# heartbeat ne puisse tourner.
_LOCK_ACQUIRE_TIMEOUT_S = 60
# TTL de régime croisière, renouvelé à chaque vérification should_stop().
_LOCK_HEARTBEAT_TTL_S = 30
_STOP_CHECK_INTERVAL_S = 5.0

_RECONNECT_INITIAL_BACKOFF_S = 5.0
_RECONNECT_MAX_BACKOFF_S = 60.0
# Durée de connexion sans erreur au-delà de laquelle une nouvelle coupure est
# traitée comme un incident isolé (backoff remis à zéro) plutôt que comme la
# continuation d'une série de coupures rapprochées.
_STABLE_CONNECTION_S = 30.0


def _make_stop_checker(camera_id: int, lock_key: str) -> Callable[[], bool]:
    """Vérifie Camera.is_active et renouvelle le verrou toutes les
    _STOP_CHECK_INTERVAL_S secondes réelles seulement (pas à chaque frame)."""
    state = {"last_check_at": 0.0}

    def should_stop() -> bool:
        now = time.monotonic()
        if now - state["last_check_at"] < _STOP_CHECK_INTERVAL_S:
            return False
        state["last_check_at"] = now

        is_active = Camera.objects.filter(pk=camera_id, is_active=True).exists()
        if not is_active:
            return True

        # Verrou déjà expiré/évincé (ex. Redis sous pression mémoire, ou
        # heartbeat manqué trop longtemps) : traité comme un arrêt fatal
        # plutôt que de continuer à streamer en croyant à tort détenir
        # encore le verrou, ce qui autoriserait une seconde tâche à
        # s'exécuter en parallèle sur la même caméra sans le savoir.
        return not cache.touch(lock_key, _LOCK_HEARTBEAT_TTL_S)

    return should_stop


def _run_with_reconnect(camera: Camera, should_stop: Callable[[], bool]) -> None:
    """Relance run_live_pipeline_for_camera après une coupure de flux, avec
    backoff exponentiel, jusqu'à ce que should_stop() indique un arrêt
    volontaire (caméra désactivée ou verrou perdu)."""
    backoff = _RECONNECT_INITIAL_BACKOFF_S
    while not should_stop():
        attempt_started_at = time.monotonic()
        try:
            run_live_pipeline_for_camera(camera, should_stop=should_stop)
            return
        except (StreamConnectionError, StreamReadError):
            logger.warning(
                "Flux interrompu pour la caméra %s, reconnexion dans %.0fs.",
                camera.pk,
                backoff,
                exc_info=True,
            )
            if should_stop():
                return
            if time.monotonic() - attempt_started_at >= _STABLE_CONNECTION_S:
                backoff = _RECONNECT_INITIAL_BACKOFF_S
            time.sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_MAX_BACKOFF_S)


@shared_task(bind=True, time_limit=None, soft_time_limit=None)
def run_camera_stream(self, camera_id: int) -> str:
    lock_key = _LOCK_KEY_TEMPLATE.format(camera_id=camera_id)
    if not cache.add(lock_key, self.request.id, timeout=_LOCK_ACQUIRE_TIMEOUT_S):
        return f"Ingestion déjà en cours pour la caméra {camera_id}."

    try:
        camera = Camera.objects.get(pk=camera_id, is_active=True)
    except Camera.DoesNotExist:
        cache.delete(lock_key)
        return f"Caméra {camera_id} introuvable ou inactive."

    try:
        _run_with_reconnect(camera, should_stop=_make_stop_checker(camera_id, lock_key))
    finally:
        cache.delete(lock_key)
    return f"Ingestion arrêtée pour « {camera.name} »."


@shared_task
def purge_stale_detections() -> int:
    """Tâche planifiée (CELERY_BEAT_SCHEDULE) : adaptateur fin sur
    apps.detection.services.purge_detections_without_infraction, qui porte
    la logique métier de purge RGPD/APDP."""
    return purge_detections_without_infraction(settings.DETECTION_RETENTION_DAYS)
