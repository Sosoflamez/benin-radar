"""Fixtures partagées pour les tests de apps.anpr (Django et pipeline
standalone)."""

from __future__ import annotations

import numpy as np
import pytest

from apps.anpr.pipeline.types import PlateCandidate


class FakePlateReader:
    """Lecteur OCR de test : renvoie une séquence de résultats prédéfinis, un
    par appel successif à .read(), aucun poids EasyOCR requis."""

    def __init__(self, results_by_call: list[list[PlateCandidate]]) -> None:
        self._results_by_call = list(results_by_call)
        self.calls: list[np.ndarray] = []

    def read(self, image: np.ndarray) -> list[PlateCandidate]:
        self.calls.append(image)
        index = len(self.calls) - 1
        if index < len(self._results_by_call):
            return self._results_by_call[index]
        return []


@pytest.fixture
def fake_plate_reader_factory():
    """Fabrique un FakePlateReader à partir d'une séquence de résultats, un
    par appel successif à .read()."""

    def _factory(results_by_call: list[list[PlateCandidate]]) -> FakePlateReader:
        return FakePlateReader(results_by_call)

    return _factory
