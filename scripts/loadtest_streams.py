#!/usr/bin/env python
"""Test de charge : combien de flux caméra simultanés cette machine absorbe en
gardant le traitement temps réel — sert à dimensionner `--concurrency` du
service `worker-streams` (docker-compose.yml) selon le nombre réel de caméras.

Simule N tâches `run_camera_stream` concurrentes via des processus séparés
(même isolation mémoire qu'un pool Celery prefork), chacune traitant la vidéo
de test en boucle simple (sans la couche Celery/verrou Redis, pour isoler le
coût CPU brut du pipeline). Balaie les paliers de concurrence donnés et
s'arrête au premier palier qui décroche du temps réel.

Usage :
    python scripts/loadtest_streams.py --video tests/fixtures/videos/sample.mp4 \\
        [--concurrencies 1,2,4,8]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

import cv2  # noqa: E402

from apps.detection.pipeline.runner import run_pipeline  # noqa: E402
from apps.detection.pipeline.types import CalibrationData  # noqa: E402
from apps.detection.services import pipeline_config_from_settings  # noqa: E402

_DEFAULT_CALIBRATION = CalibrationData(
    homography_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    reference_points=[[0, 0], [10, 0], [10, 10], [0, 10]],
    measured_distance_m=20.0,
)


def _process_one_stream(video_path_str: str) -> float:
    """Traite la vidéo dans un processus séparé (simule un worker Celery
    prefork traitant `run_camera_stream`) ; retourne la durée du traitement."""
    config = pipeline_config_from_settings()
    started_at = time.perf_counter()
    run_pipeline(Path(video_path_str), _DEFAULT_CALIBRATION, config)
    return time.perf_counter() - started_at


def _video_duration_s(video_path: Path) -> float:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Impossible d'ouvrir la vidéo : {video_path}")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    return total_frames / fps if fps else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--video", required=True, help="Fichier vidéo à traiter (répété N fois).")
    parser.add_argument(
        "--concurrencies",
        default="1,2,4,8",
        help="Paliers de flux simultanés à tester, séparés par des virgules.",
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Erreur : fichier introuvable : {video_path}", file=sys.stderr)
        raise SystemExit(1)

    duration_s = _video_duration_s(video_path)
    concurrencies = [int(n) for n in args.concurrencies.split(",")]

    print(
        f"Vidéo de {duration_s:.2f}s — {os.cpu_count()} cœurs CPU disponibles sur cette machine.\n"
    )

    last_ok_concurrency = 0
    for concurrency in concurrencies:
        started_at = time.perf_counter()
        with ProcessPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(_process_one_stream, str(video_path)) for _ in range(concurrency)
            ]
            per_stream_times = [future.result() for future in as_completed(futures)]
        wall_clock_s = time.perf_counter() - started_at

        slowest_stream_s = max(per_stream_times)
        real_time_ok = slowest_stream_s <= duration_s

        print(
            f"[concurrency={concurrency}] pire flux : {slowest_stream_s:.2f}s "
            f"(mur : {wall_clock_s:.2f}s) — temps réel : {'OK' if real_time_ok else 'NON'} "
            f"(vidéo de {duration_s:.2f}s)"
        )

        if not real_time_ok:
            print(f"\n-> décroche du temps réel au-delà de {last_ok_concurrency} flux simultanés.")
            break
        last_ok_concurrency = concurrency
    else:
        print(
            f"\n-> temps réel tenu jusqu'à {last_ok_concurrency} flux simultanés "
            "(palier le plus haut testé)."
        )


if __name__ == "__main__":
    main()
