from __future__ import annotations

import factory
from django.utils import timezone

from apps.cameras.factories import CameraFactory
from apps.detection.models import VehicleDetection


class VehicleDetectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VehicleDetection

    camera = factory.SubFactory(CameraFactory)
    track_id = factory.Sequence(lambda n: n + 1)
    vehicle_class = VehicleDetection.VehicleClass.MOTORCYCLE
    zone_entered_at = factory.LazyFunction(timezone.now)
    zone_exited_at = factory.LazyAttribute(
        lambda o: o.zone_entered_at + timezone.timedelta(seconds=1)
    )
    computed_speed_kmh = "72.0"
    tracking_confidence = "0.950"
    bbox = factory.LazyFunction(lambda: [10, 20, 110, 220])
