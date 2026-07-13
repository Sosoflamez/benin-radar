"""Dataclasses du pipeline ANPR. Aucune dépendance Django : ce module doit
rester utilisable de façon autonome (voir apps/anpr/services.py pour la
persistance)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class PlateCandidate:
    text: str
    confidence: float
    polygon: list[tuple[float, float]]


@dataclass(frozen=True)
class PlateReadResult:
    raw_text: str
    normalized_plate: str | None
    confidence: float
    # Toujours renseigné (jamais None) : au pire le crop véhicule prétraité,
    # pour garder une valeur probante même sans lecture exploitable.
    plate_crop: np.ndarray = field(compare=False, repr=False)
