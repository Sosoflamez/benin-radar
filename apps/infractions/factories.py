from __future__ import annotations

import factory
from django.contrib.auth import get_user_model

from apps.anpr.factories import PlateReadingFactory
from apps.cameras.factories import CameraFactory
from apps.detection.factories import VehicleDetectionFactory
from apps.infractions.models import Evidence, Infraction


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"agent{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@benin-radar.bj")


class InfractionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Infraction

    camera = factory.SubFactory(CameraFactory)
    detection = factory.SubFactory(
        VehicleDetectionFactory, camera=factory.SelfAttribute("..camera")
    )
    plate = factory.SubFactory(PlateReadingFactory)
    recorded_speed_kmh = "85.0"
    speed_limit_kmh = 60
    status = Infraction.Status.DETECTEE


class EvidenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Evidence

    infraction = factory.SubFactory(InfractionFactory)
    full_image = factory.django.ImageField(filename="evidence.jpg", width=640, height=480)
    sha256_hash = factory.Faker("sha256")
