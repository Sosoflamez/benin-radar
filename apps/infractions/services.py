from __future__ import annotations

import hashlib

from django.core.files.base import File

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
