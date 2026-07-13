from __future__ import annotations

import hashlib
from decimal import Decimal

import cv2
import numpy as np
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile, File

from apps.detection.models import VehicleDetection
from apps.infractions.models import Evidence, EvidenceAccessLog, Infraction

User = get_user_model()


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
    from apps.dashboard.services import broadcast_new_infraction

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
    broadcast_new_infraction(infraction)
    return infraction


def transition_to_verified(infraction: Infraction, agent: User) -> Infraction:
    """Premier contrôle par un agent : detectee -> verifiee (workflow de
    validation, Phase 4). Lève PermissionDenied si l'agent n'a pas la
    permission dédiée, ValidationError si l'infraction n'est pas au statut
    attendu."""
    if not agent.has_perm("infractions.verify_infraction"):
        raise PermissionDenied("Permission de vérification des infractions requise.")
    if infraction.status != Infraction.Status.DETECTEE:
        raise ValidationError(
            f"Seule une infraction « détectée » peut être vérifiée (statut actuel : "
            f"« {infraction.status} »)."
        )
    infraction.status = Infraction.Status.VERIFIEE
    infraction.save(update_fields=["status", "updated_at"])
    return infraction


def _transition_to_final_status(
    infraction: Infraction, supervisor: User, target_status: str
) -> Infraction:
    if not supervisor.has_perm("infractions.validate_infraction"):
        raise PermissionDenied("Permission de validation des infractions requise.")
    if infraction.status != Infraction.Status.VERIFIEE:
        raise ValidationError(
            f"Seule une infraction « vérifiée » peut être validée ou rejetée (statut actuel : "
            f"« {infraction.status} »)."
        )
    infraction.status = target_status
    infraction.validated_by = supervisor
    infraction.save(update_fields=["status", "validated_by", "updated_at"])
    return infraction


def transition_to_validated(infraction: Infraction, supervisor: User) -> Infraction:
    """Décision finale d'un superviseur : verifiee -> validee."""
    return _transition_to_final_status(infraction, supervisor, Infraction.Status.VALIDEE)


def transition_to_rejected(infraction: Infraction, supervisor: User) -> Infraction:
    """Décision finale d'un superviseur : verifiee -> rejetee. L'infraction
    n'est jamais supprimée (CLAUDE.md), seulement marquée rejetée."""
    return _transition_to_final_status(infraction, supervisor, Infraction.Status.REJETEE)


def log_evidence_access(evidence: Evidence, user: User) -> EvidenceAccessLog:
    """Journalise une consultation de preuve (APDP, CLAUDE.md — accès
    réservé aux agents authentifiés, chaque consultation journalisée)."""
    if not user.has_perm("infractions.view_evidence"):
        raise PermissionDenied("Permission de consultation des preuves requise.")
    return EvidenceAccessLog.objects.create(evidence=evidence, accessed_by=user)
