#!/usr/bin/env python
"""Mesure la performance du pipeline vision sur un fichier vidéo.

À exécuter avant/après toute modification du pipeline (règle CLAUDE.md).

Usage :
    python scripts/benchmark_pipeline.py --video tests/fixtures/videos/sample.mp4 \\
        [--camera "Cotonou Boulevard"] [--runs 3]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

import cv2  # noqa: E402

from apps.cameras.models import Camera  # noqa: E402
from apps.detection.pipeline.runner import run_pipeline  # noqa: E402
from apps.detection.pipeline.types import CalibrationData  # noqa: E402
from apps.detection.services import (  # noqa: E402
    calibration_data_from_profile,
    pipeline_config_from_settings,
)

_DEFAULT_CALIBRATION = CalibrationData(
    homography_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    reference_points=[[0, 0], [10, 0], [10, 10], [0, 10]],
    measured_distance_m=20.0,
)


def _video_stats(video_path: Path) -> tuple[float, int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Impossible d'ouvrir la vidéo : {video_path}")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    return fps, total_frames


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--video", required=True, help="Fichier vidéo à traiter.")
    parser.add_argument(
        "--camera", default=None, help="Caméra dont utiliser la calibration réelle."
    )
    parser.add_argument("--runs", type=int, default=1, help="Nombre de répétitions.")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Erreur : fichier introuvable : {video_path}", file=sys.stderr)
        raise SystemExit(1)

    if args.camera:
        camera = Camera.objects.get(name=args.camera)
        calibration = calibration_data_from_profile(camera.calibration_profile)
    else:
        calibration = _DEFAULT_CALIBRATION

    config = pipeline_config_from_settings()
    source_fps, total_frames = _video_stats(video_path)
    duration_s = total_frames / source_fps if source_fps else 0.0

    for run in range(1, args.runs + 1):
        started_at = time.perf_counter()
        estimates = run_pipeline(video_path, calibration, config)
        elapsed_s = time.perf_counter() - started_at

        processed_frames = round(duration_s * config.sample_fps) if duration_s else 0
        effective_fps = processed_frames / elapsed_s if elapsed_s else 0.0
        real_time_ok = elapsed_s <= duration_s if duration_s else False

        print(
            f"[run {run}/{args.runs}] {processed_frames} frames traitées en {elapsed_s:.2f}s "
            f"({effective_fps:.1f} FPS effectif) — {len(estimates)} véhicule(s) détecté(s) — "
            f"temps réel : {'OK' if real_time_ok else 'NON'} "
            f"(vidéo de {duration_s:.2f}s à {source_fps:.1f} FPS natif)"
        )


if __name__ == "__main__":
    main()
