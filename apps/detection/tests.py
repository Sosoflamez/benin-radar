import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.detection.admin import VehicleDetectionAdmin
from apps.detection.factories import VehicleDetectionFactory
from apps.detection.models import VehicleDetection


@pytest.mark.django_db
class TestVehicleDetection:
    def test_str_contains_camera_and_speed(self):
        detection = VehicleDetectionFactory(
            camera__name="Porto-Novo Ouando", computed_speed_kmh="72.0"
        )
        text = str(detection)
        assert "Porto-Novo Ouando" in text
        assert "72.0" in text

    def test_most_recent_detection_first(self):
        first = VehicleDetectionFactory()
        second = VehicleDetectionFactory()
        assert list(VehicleDetection.objects.all()) == [second, first]


@pytest.mark.django_db
class TestVehicleDetectionAdmin:
    def test_detections_cannot_be_added_manually(self):
        admin = VehicleDetectionAdmin(VehicleDetection, AdminSite())
        request = RequestFactory().get("/")
        request.user = get_user_model().objects.create_superuser(
            username="root", email="root@benin-radar.bj", password="pw"
        )
        assert admin.has_add_permission(request) is False

    def test_all_fields_are_readonly(self):
        admin = VehicleDetectionAdmin(VehicleDetection, AdminSite())
        field_names = {f.name for f in VehicleDetection._meta.fields}
        assert set(admin.readonly_fields) == field_names
