#!/usr/bin/env python
"""Génère un clip vidéo synthétique pour les besoins de benchmark/test de charge.

Dessine des rectangles colorés en mouvement horizontal (véhicules simulés) sur
fond uni. Utile pour mesurer le débit/temps réel du pipeline (capture,
détection, tracking) sans dépendre d'un vrai flux caméra — YOLO ne détectera
vraisemblablement aucun « vrai » véhicule sur ce clip, ce n'est pas son but.

Usage : python scripts/generate_synthetic_video.py [--output tests/fixtures/videos/sample.mp4]
    [--duration-s 8] [--fps 15] [--width 1280] [--height 720] [--vehicles 3]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "tests" / "fixtures" / "videos" / "sample.mp4"

_BACKGROUND_COLOR = (60, 60, 60)
_VEHICLE_COLORS = [(66, 135, 245), (66, 245, 138), (245, 176, 66)]
_VEHICLE_SIZE = (90, 50)


def generate_synthetic_video(
    output_path: Path = DEFAULT_OUTPUT,
    duration_s: float = 8.0,
    fps: int = 15,
    width: int = 1280,
    height: int = 720,
    vehicle_count: int = 3,
) -> Path:
    """Écrit un clip de `duration_s` secondes vers output_path, retourne ce chemin."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = round(duration_s * fps)

    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise OSError(f"Impossible d'écrire la vidéo : {output_path}")

    vehicle_w, vehicle_h = _VEHICLE_SIZE
    try:
        for frame_idx in range(total_frames):
            frame = np.full((height, width, 3), _BACKGROUND_COLOR, dtype=np.uint8)
            progress = frame_idx / max(total_frames - 1, 1)
            for vehicle_idx in range(vehicle_count):
                lane_y = int(height * (vehicle_idx + 1) / (vehicle_count + 1))
                x = int(-vehicle_w + progress * (width + 2 * vehicle_w))
                color = _VEHICLE_COLORS[vehicle_idx % len(_VEHICLE_COLORS)]
                cv2.rectangle(
                    frame, (x, lane_y), (x + vehicle_w, lane_y + vehicle_h), color, thickness=-1
                )
            writer.write(frame)
    finally:
        writer.release()

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Fichier vidéo de sortie.")
    parser.add_argument("--duration-s", type=float, default=8.0, help="Durée du clip en secondes.")
    parser.add_argument("--fps", type=int, default=15, help="Images par seconde.")
    parser.add_argument("--width", type=int, default=1280, help="Largeur en pixels.")
    parser.add_argument("--height", type=int, default=720, help="Hauteur en pixels.")
    parser.add_argument(
        "--vehicles", type=int, default=3, help="Nombre de rectangles simulant des véhicules."
    )
    args = parser.parse_args()

    output_path = generate_synthetic_video(
        output_path=Path(args.output),
        duration_s=args.duration_s,
        fps=args.fps,
        width=args.width,
        height=args.height,
        vehicle_count=args.vehicles,
    )
    print(f"Vidéo synthétique écrite : {output_path}")


if __name__ == "__main__":
    main()
