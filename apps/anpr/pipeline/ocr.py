"""Orchestration standalone de la lecture de plaque : prétraitement -> OCR ->
normalisation. Ne dépend pas de Django."""

from __future__ import annotations

import numpy as np

from apps.anpr.pipeline.preprocess import enhance_crop, rectify_candidate
from apps.anpr.pipeline.reader import EasyOcrPlateReader, PlateReader
from apps.anpr.pipeline.types import PlateCandidate, PlateReadResult
from apps.anpr.plates import normalize_plate


def _best_result(candidates: list[PlateCandidate], fallback_crop: np.ndarray) -> PlateReadResult:
    for candidate in sorted(candidates, key=lambda c: c.confidence, reverse=True):
        normalized = normalize_plate(candidate.text)
        if normalized is not None:
            return PlateReadResult(candidate.text, normalized, candidate.confidence, fallback_crop)
    if candidates:
        best = max(candidates, key=lambda c: c.confidence)
        return PlateReadResult(best.text, None, best.confidence, fallback_crop)
    return PlateReadResult("", None, 0.0, fallback_crop)


def read_plate(vehicle_crop: np.ndarray, reader: PlateReader | None = None) -> PlateReadResult:
    """Lit la plaque d'un crop véhicule. Ne devine jamais un caractère hors
    format (voir apps.anpr.plates.normalize_plate) : si aucun candidat OCR ne
    matche le format béninois, le résultat est marqué illisible plutôt que
    corrigé au hasard."""
    if reader is None:
        reader = EasyOcrPlateReader()

    enhanced = enhance_crop(vehicle_crop)
    candidates = reader.read(enhanced)
    result = _best_result(candidates, fallback_crop=enhanced)
    if result.normalized_plate is not None or not candidates:
        return result

    # 2e passe : redressement du meilleur candidat, seulement si la 1re
    # passe a échoué (borne le coût d'inférence supplémentaire au cas
    # d'échec, pas au chemin nominal).
    best = max(candidates, key=lambda c: c.confidence)
    rectified = rectify_candidate(enhanced, best.polygon)
    retry = _best_result(reader.read(rectified), fallback_crop=rectified)
    return retry if retry.normalized_plate is not None else result
