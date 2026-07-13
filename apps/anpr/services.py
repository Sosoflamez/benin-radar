"""Persistance du pipeline ANPR dans les modèles Django (Phase 3)."""

from __future__ import annotations

from decimal import Decimal

import cv2
import numpy as np
from django.conf import settings
from django.core.files.base import ContentFile

from apps.anpr.models import PlateReading
from apps.anpr.pipeline.ocr import read_plate
from apps.anpr.pipeline.reader import EasyOcrPlateReader, PlateReader
from apps.infractions.models import Evidence, Infraction


def _default_reader() -> PlateReader:
    return EasyOcrPlateReader(gpu=settings.ANPR_EASYOCR_GPU)


def _decode_image(image_field) -> np.ndarray:
    image_field.open()
    buffer = np.frombuffer(image_field.read(), dtype=np.uint8)
    image_field.seek(0)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _crop_bbox(image: np.ndarray, bbox: list[float]) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = bbox
    left = max(0, min(int(x1), width - 1))
    top = max(0, min(int(y1), height - 1))
    right = max(left + 1, min(int(x2), width))
    bottom = max(top + 1, min(int(y2), height))
    crop = image[top:bottom, left:right]
    return crop if crop.size else image


def _encode_jpeg(image: np.ndarray, name: str) -> ContentFile:
    _, buffer = cv2.imencode(".jpg", image)
    return ContentFile(buffer.tobytes(), name=name)


def create_plate_reading_from_evidence(
    evidence: Evidence, reader: PlateReader | None = None
) -> PlateReading:
    """Lit la plaque du véhicule photographié dans `evidence.full_image` et
    persiste le résultat. Lie l'Infraction et passe son statut à VERIFIEE
    seulement si la plaque est lisible — une plaque illisible laisse
    l'infraction à DETECTEE pour revue humaine du cliché brut."""
    detection = evidence.infraction.detection
    full_image = _decode_image(evidence.full_image)
    vehicle_crop = _crop_bbox(full_image, detection.bbox)
    result = read_plate(vehicle_crop, reader=reader or _default_reader())

    status = (
        PlateReading.Status.LISIBLE if result.normalized_plate else PlateReading.Status.ILLISIBLE
    )
    plate_reading = PlateReading.objects.create(
        detection=detection,
        raw_plate=result.raw_text,
        normalized_plate=result.normalized_plate or "",
        status=status,
        ocr_confidence=Decimal(str(round(result.confidence, 3))),
        plate_crop=_encode_jpeg(result.plate_crop, f"plate_{detection.id}.jpg"),
    )

    evidence.plate_crop_image = _encode_jpeg(result.plate_crop, f"plate_{detection.id}.jpg")
    evidence.save(update_fields=["plate_crop_image"])

    if status == PlateReading.Status.LISIBLE:
        infraction = evidence.infraction
        infraction.plate = plate_reading
        infraction.status = Infraction.Status.VERIFIEE
        infraction.save(update_fields=["plate", "status"])

    return plate_reading
