import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory

from apps.anpr.admin import PlateReadingAdmin
from apps.anpr.factories import PlateReadingFactory
from apps.anpr.models import PlateReading
from apps.anpr.plates import normalize_plate


class TestNormalizePlate:
    def test_accepts_well_formed_plate(self):
        assert normalize_plate("AB 1234 RB") == "AB 1234 RB"

    def test_accepts_plate_without_spaces(self):
        assert normalize_plate("ab1234rb") == "AB 1234 RB"

    def test_corrects_ocr_confusions_in_typed_positions(self):
        # "0" et "8" lus par l'OCR à la place de lettres, "O" à la place d'un chiffre.
        assert normalize_plate("08 1234 R8") == "OB 1234 RB"
        assert normalize_plate("AB 123O RB") == "AB 1230 RB"

    def test_rejects_wrong_length(self):
        assert normalize_plate("AB 123 RB") is None
        assert normalize_plate("AB 12345 RB") is None

    def test_rejects_unrecognizable_format(self):
        assert normalize_plate("1234ABAB") is None

    def test_never_guesses_a_missing_character(self):
        assert normalize_plate("") is None
        assert normalize_plate("A") is None


@pytest.mark.django_db
class TestPlateReading:
    def test_str_returns_normalized_plate(self):
        reading = PlateReadingFactory(normalized_plate="AB 1234 RB")
        assert str(reading) == "AB 1234 RB"

    def test_str_falls_back_when_illisible(self):
        reading = PlateReadingFactory(normalized_plate="", status=PlateReading.Status.ILLISIBLE)
        assert str(reading) == f"illisible ({reading.detection_id})"


@pytest.mark.django_db
class TestPlateReadingAdmin:
    def _request_for(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_denied_without_view_plate_data_permission(self):
        admin = PlateReadingAdmin(PlateReading, AdminSite())
        user = get_user_model().objects.create_user(username="agent", password="pw", is_staff=True)
        user.user_permissions.add(
            Permission.objects.get(codename="view_platereading", content_type__app_label="anpr")
        )
        assert admin.has_view_permission(self._request_for(user)) is False

    def test_allowed_with_view_plate_data_and_default_permission(self):
        admin = PlateReadingAdmin(PlateReading, AdminSite())
        user = get_user_model().objects.create_user(username="agent2", password="pw", is_staff=True)
        user.user_permissions.add(
            Permission.objects.get(codename="view_platereading", content_type__app_label="anpr"),
            Permission.objects.get(codename="view_plate_data", content_type__app_label="anpr"),
        )
        assert admin.has_view_permission(self._request_for(user)) is True
