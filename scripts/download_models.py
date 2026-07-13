#!/usr/bin/env python
"""Télécharge les poids YOLO nécessaires au pipeline vision dans ml_models/.

Usage : python scripts/download_models.py [--weights yolov8n.pt] [--target-dir ml_models]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_DIR = REPO_ROOT / "ml_models"


def download_weights(
    weights_name: str = "yolov8n.pt", target_dir: Path = DEFAULT_TARGET_DIR
) -> Path:
    """Télécharge (si absent) les poids YOLO vers target_dir, retourne le
    chemin local des poids."""
    target_dir.mkdir(parents=True, exist_ok=True)
    weights_path = target_dir / weights_name
    YOLO(str(weights_path))  # télécharge vers weights_path si le fichier n'existe pas encore
    return weights_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", default="yolov8n.pt", help="Nom des poids YOLO à télécharger.")
    parser.add_argument("--target-dir", default=str(DEFAULT_TARGET_DIR), help="Répertoire cible.")
    args = parser.parse_args()

    weights_path = download_weights(args.weights, Path(args.target_dir))
    print(f"Poids disponibles : {weights_path}")


if __name__ == "__main__":
    main()
