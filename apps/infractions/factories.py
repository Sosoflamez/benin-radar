from __future__ import annotations

import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

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


class AgentUserFactory(UserFactory):
    """Utilisateur membre du groupe « Agents » (migration
    0004_supervisors_group) : peut consulter les preuves/plaques et faire
    passer une infraction detectee -> verifiee."""

    class Meta:
        model = get_user_model()
        django_get_or_create = ("username",)
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"agent-user{n}")

    @factory.post_generation
    def _join_agents_group(self, create, extracted, **kwargs) -> None:
        if create:
            self.groups.add(Group.objects.get(name="Agents"))


class SupervisorUserFactory(UserFactory):
    """Utilisateur membre du groupe « Superviseurs » : seul habilité à
    valider ou rejeter une infraction vérifiée."""

    class Meta:
        model = get_user_model()
        django_get_or_create = ("username",)
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"supervisor-user{n}")

    @factory.post_generation
    def _join_supervisors_group(self, create, extracted, **kwargs) -> None:
        if create:
            self.groups.add(Group.objects.get(name="Superviseurs"))


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
