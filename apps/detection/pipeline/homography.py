"""Calcul et application de l'homographie image -> plan monde.

Convention d'ordre des 4 points de référence : proche-gauche, proche-droite,
loin-droite, loin-gauche (dans le sens de la marche du véhicule). Le
rectangle monde correspondant est [[0,0],[W,0],[W,D],[0,D]] où W est la
largeur de voie et D la distance réelle mesurée entre les deux lignes
virtuelles.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np


def compute_homography(
    reference_points: Sequence[Sequence[float]],
    lane_width_m: float,
    measured_distance_m: float,
) -> list[list[float]]:
    """Calcule la matrice d'homographie 3x3 à partir de 4 points image et du
    rectangle monde qu'ils délimitent."""
    src = np.array(reference_points, dtype=np.float32)
    dst = np.array(
        [
            [0.0, 0.0],
            [lane_width_m, 0.0],
            [lane_width_m, measured_distance_m],
            [0.0, measured_distance_m],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(src, dst)
    return matrix.tolist()


def image_point_to_world(
    point: tuple[float, float], homography_matrix: Sequence[Sequence[float]]
) -> tuple[float, float]:
    """Projette un point image (x, y) en coordonnées monde (mètres)."""
    matrix = np.array(homography_matrix, dtype=np.float64)
    x, y = point
    vector = matrix @ np.array([x, y, 1.0])
    return float(vector[0] / vector[2]), float(vector[1] / vector[2])
