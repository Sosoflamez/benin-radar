from __future__ import annotations

import factory
from django.utils import timezone

from apps.cameras.models import CalibrationProfile, Camera


class CameraFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Camera

    name = factory.Sequence(lambda n: f"Caméra {n}")
    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")
    stream_url = factory.Faker("file_path", extension="mp4")
    speed_limit_kmh = 60
    is_active = True


class CalibrationProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CalibrationProfile

    camera = factory.SubFactory(CameraFactory)
    homography_matrix = factory.LazyFunction(lambda: [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    reference_points = factory.LazyFunction(lambda: [[0, 0], [10, 0], [10, 10], [0, 10]])
    measured_distance_m = "20.00"
    calibrated_at = factory.LazyFunction(timezone.now)
