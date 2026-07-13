import pytest
from django.db import IntegrityError

from apps.cameras.factories import CalibrationProfileFactory, CameraFactory
from apps.cameras.models import Camera


@pytest.mark.django_db
class TestCamera:
    def test_str_returns_name(self):
        camera = CameraFactory(name="Godomey PK10")
        assert str(camera) == "Godomey PK10"

    def test_name_is_unique(self):
        CameraFactory(name="Calavi Zogbo")
        with pytest.raises(IntegrityError):
            CameraFactory(name="Calavi Zogbo")

    def test_default_ordering_is_by_name(self):
        CameraFactory(name="Zogbo")
        CameraFactory(name="Akpakpa")
        names = list(Camera.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestCalibrationProfile:
    def test_one_profile_per_camera(self):
        camera = CameraFactory()
        CalibrationProfileFactory(camera=camera)
        with pytest.raises(IntegrityError):
            CalibrationProfileFactory(camera=camera)

    def test_str_contains_camera_name(self):
        camera = CameraFactory(name="Cotonou Ganhi")
        profile = CalibrationProfileFactory(camera=camera)
        assert "Cotonou Ganhi" in str(profile)
