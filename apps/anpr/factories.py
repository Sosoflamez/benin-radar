from __future__ import annotations

import factory

from apps.anpr.models import PlateReading
from apps.detection.factories import VehicleDetectionFactory


class PlateReadingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PlateReading

    detection = factory.SubFactory(VehicleDetectionFactory)
    raw_plate = "AB 1234 RB"
    normalized_plate = "AB 1234 RB"
    status = PlateReading.Status.LISIBLE
    ocr_confidence = "0.900"
    plate_crop = factory.django.ImageField(filename="plate.jpg", width=80, height=40)
