from __future__ import annotations

import hashlib
from decimal import Decimal

import cv2
import numpy as np
from django.conf import settings
from django.core.files.base import ContentFile, File

from apps.detection.models import VehicleDetection
from apps.infractions.models import Evidence, Infraction


def create_evidence(
    infraction: Infraction,
    full_image: File,
    plate_crop_image: File | None = None,
    metadata: dict | None = None,
) -> Evidence:
    """Crée une preuve d'infraction et calcule son hash SHA-256 d'intégrité."""
    digest = hashlib.sha256()
    for chunk in full_image.chunks():
        digest.update(chunk)
    full_image.seek(0)

    return Evidence.objects.create(
        infraction=infraction,
        full_image=full_image,
        plate_crop_image=plate_crop_image or "",
        sha256_hash=digest.hexdigest(),
        metadata=metadata or {},
    )


def evaluate_detection_for_infraction(
    detection: VehicleDetection, exit_frame: np.ndarray | None
) -> Infraction | None:
    """Applique la règle de déclenchement (CLAUDE.md, pipeline étape 5) : si
    la vitesse dépasse limite + tolérance, crée l'Infraction et sa preuve
    photographique, puis lance la lecture de plaque en tâche de fond.

    Ne crée jamais d'Infraction sans preuve : si `exit_frame` est absent,
    retourne None sans rien persister plutôt que d'enregistrer une
    infraction sans valeur probante."""
    from apps.anpr.tasks import read_plate_for_evidence

    # str() puis Decimal() : robuste que computed_speed_kmh soit déjà un
    # Decimal (rechargé depuis la base) ou une chaîne (instance en mémoire,
    # non rafraîchie).
    recorded_speed_kmh = Decimal(str(detection.computed_speed_kmh))
    threshold = detection.camera.speed_limit_kmh + settings.SPEED_TOLERANCE_KMH
    if recorded_speed_kmh <= threshold or exit_frame is None:
        return None

    infraction = Infraction.objects.create(
        detection=detection,
        camera=detection.camera,
        recorded_speed_kmh=recorded_speed_kmh,
        speed_limit_kmh=detection.camera.speed_limit_kmh,
    )
    _, buffer = cv2.imencode(".jpg", exit_frame)
    full_image = ContentFile(buffer.tobytes(), name=f"infraction_{infraction.id}.jpg")
    evidence = create_evidence(infraction, full_image=full_image)
    read_plate_for_evidence.delay(evidence.id)
    return infraction
