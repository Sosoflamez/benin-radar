"""Lecture de texte par OCR. `PlateReader` est un Protocol pour permettre
l'injection d'un faux lecteur en test, sans charger de poids EasyOCR réels
(téléchargement réseau au premier chargement)."""

from __future__ import annotations

from typing import Protocol

import easyocr
import numpy as np

from apps.anpr.pipeline.types import PlateCandidate


class PlateReader(Protocol):
    def read(self, image: np.ndarray) -> list[PlateCandidate]: ...


class EasyOcrPlateReader:
    """Lecteur EasyOCR. Les poids sont chargés dans __init__, jamais à
    l'import du module — les tests injectent un faux lecteur et ne
    construisent jamais cette classe."""

    def __init__(self, gpu: bool = False) -> None:
        self._reader = easyocr.Reader(["en"], gpu=gpu)

    def read(self, image: np.ndarray) -> list[PlateCandidate]:
        return [
            PlateCandidate(
                text=text,
                confidence=float(confidence),
                polygon=[(float(x), float(y)) for x, y in polygon],
            )
            for polygon, text, confidence in self._reader.readtext(image)
        ]
