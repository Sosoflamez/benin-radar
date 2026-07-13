"""Prétraitement OpenCV du crop véhicule avant OCR (CLAUDE.md étape 6 :
redressement, contraste)."""

from __future__ import annotations

import cv2
import numpy as np


def enhance_crop(image: np.ndarray, min_height: int = 60) -> np.ndarray:
    """Améliore le contraste (CLAHE) et agrandit le crop s'il est trop petit
    pour une lecture OCR fiable."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    height = enhanced.shape[0]
    if height < min_height and height > 0:
        scale = min_height / height
        enhanced = cv2.resize(enhanced, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def rectify_candidate(
    image: np.ndarray,
    polygon: list[tuple[float, float]],
    output_size: tuple[int, int] = (200, 50),
) -> np.ndarray:
    """Redresse la région d'un candidat OCR par transformation de
    perspective. `polygon` est un quadrilatère [haut-gauche, haut-droit,
    bas-droit, bas-gauche], ordre renvoyé par EasyOCR."""
    width, height = output_size
    source = np.array(polygon, dtype=np.float32)
    destination = np.array(
        [[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32
    )
    matrix = cv2.getPerspectiveTransform(source, destination)
    return cv2.warpPerspective(image, matrix, (width, height))
