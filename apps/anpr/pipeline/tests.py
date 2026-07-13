"""Tests du pipeline ANPR standalone (aucun accès base de données, aucun
poids EasyOCR réel)."""

from __future__ import annotations

import numpy as np

from apps.anpr.pipeline.ocr import read_plate
from apps.anpr.pipeline.preprocess import enhance_crop, rectify_candidate
from apps.anpr.pipeline.types import PlateCandidate

MATCHING_TEXT = "AB1234RB"
UNMATCHED_TEXT = "HELLO"
QUAD = [(10.0, 10.0), (190.0, 10.0), (190.0, 70.0), (10.0, 70.0)]


def _vehicle_crop() -> np.ndarray:
    return np.full((80, 200, 3), 128, dtype=np.uint8)


class TestEnhanceCrop:
    def test_upscales_small_crop(self):
        small = np.zeros((20, 80, 3), dtype=np.uint8)
        enhanced = enhance_crop(small, min_height=60)
        assert enhanced.shape[0] >= 60
        assert enhanced.shape[2] == 3

    def test_leaves_tall_enough_crop_size_untouched(self):
        crop = _vehicle_crop()
        enhanced = enhance_crop(crop, min_height=60)
        assert enhanced.shape[:2] == crop.shape[:2]
        assert enhanced.shape[2] == 3


class TestRectifyCandidate:
    def test_output_matches_requested_size(self):
        crop = _vehicle_crop()
        rectified = rectify_candidate(crop, QUAD, output_size=(200, 50))
        assert rectified.shape[:2] == (50, 200)


class TestReadPlate:
    def test_legible_plate_on_first_pass(self, fake_plate_reader_factory):
        reader = fake_plate_reader_factory(
            [[PlateCandidate(text=MATCHING_TEXT, confidence=0.9, polygon=QUAD)]]
        )
        result = read_plate(_vehicle_crop(), reader=reader)
        assert result.normalized_plate == "AB 1234 RB"
        assert len(reader.calls) == 1

    def test_illisible_with_unmatched_candidate(self, fake_plate_reader_factory):
        reader = fake_plate_reader_factory(
            [
                [PlateCandidate(text=UNMATCHED_TEXT, confidence=0.9, polygon=QUAD)],
                [],
            ]
        )
        result = read_plate(_vehicle_crop(), reader=reader)
        assert result.normalized_plate is None
        assert result.raw_text == UNMATCHED_TEXT
        assert result.confidence == 0.9

    def test_illisible_with_no_candidate(self, fake_plate_reader_factory):
        reader = fake_plate_reader_factory([[]])
        result = read_plate(_vehicle_crop(), reader=reader)
        assert result.normalized_plate is None
        assert result.raw_text == ""
        assert result.confidence == 0.0
        assert len(reader.calls) == 1  # pas de 2e passe sans aucun candidat

    def test_second_pass_rescues_failed_first_pass(self, fake_plate_reader_factory):
        reader = fake_plate_reader_factory(
            [
                [PlateCandidate(text=UNMATCHED_TEXT, confidence=0.9, polygon=QUAD)],
                [PlateCandidate(text=MATCHING_TEXT, confidence=0.95, polygon=QUAD)],
            ]
        )
        result = read_plate(_vehicle_crop(), reader=reader)
        assert result.normalized_plate == "AB 1234 RB"
        assert len(reader.calls) == 2
