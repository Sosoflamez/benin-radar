#!/usr/bin/env python
"""Calibre une caméra : calcule l'homographie image -> monde à partir de 4
points de référence et enregistre/actualise le CalibrationProfile associé.

Usage :
    python scripts/calibrate_camera.py --camera "Cotonou Boulevard" \\
        --points 120,400 520,400 480,120 160,120 \\
        --distance-m 25.0 --lane-width-m 3.5 [--extract-frame frame.jpg] [--video clip.mp4]

Les 4 --points sont donnés dans l'ordre proche-gauche, proche-droite,
loin-droite, loin-gauche (dans le sens de la marche des véhicules).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

import cv2  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.cameras.models import CalibrationProfile, Camera  # noqa: E402
from apps.detection.pipeline.homography import compute_homography  # noqa: E402


def _parse_point(raw: str) -> list[float]:
    x_str, _, y_str = raw.partition(",")
    return [float(x_str), float(y_str)]


def _extract_first_frame(video_path: Path, output_path: Path) -> None:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Impossible d'ouvrir la vidéo : {video_path}")
    try:
        read_ok, image = capture.read()
        if not read_ok:
            raise OSError(f"Impossible de lire une frame dans : {video_path}")
        cv2.imwrite(str(output_path), image)
    finally:
        capture.release()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--camera", required=True, help="Nom exact de la caméra à calibrer.")
    parser.add_argument(
        "--points",
        nargs=4,
        type=_parse_point,
        metavar="X,Y",
        required=True,
        help="4 points image 'x,y' : proche-gauche proche-droite loin-droite loin-gauche.",
    )
    parser.add_argument(
        "--distance-m", type=float, required=True, help="Distance réelle mesurée (m)."
    )
    parser.add_argument(
        "--lane-width-m", type=float, default=3.5, help="Largeur de voie (m), défaut 3.5."
    )
    parser.add_argument("--video", default=None, help="Vidéo dont extraire une frame de référence.")
    parser.add_argument(
        "--extract-frame", default=None, help="Chemin de sortie pour la frame extraite."
    )
    args = parser.parse_args()

    if args.extract_frame:
        if not args.video:
            parser.error("--extract-frame nécessite --video.")
        _extract_first_frame(Path(args.video), Path(args.extract_frame))
        print(f"Frame extraite : {args.extract_frame}")

    try:
        camera = Camera.objects.get(name=args.camera)
    except Camera.DoesNotExist:
        print(f"Erreur : caméra introuvable : « {args.camera} ».", file=sys.stderr)
        raise SystemExit(1) from None

    homography_matrix = compute_homography(args.points, args.lane_width_m, args.distance_m)

    profile, created = CalibrationProfile.objects.update_or_create(
        camera=camera,
        defaults={
            "homography_matrix": homography_matrix,
            "reference_points": args.points,
            "measured_distance_m": args.distance_m,
            "calibrated_at": timezone.now(),
        },
    )
    action = "créé" if created else "mis à jour"
    print(f"Profil de calibration {action} pour « {camera.name} » (id={profile.pk}).")


if __name__ == "__main__":
    main()
