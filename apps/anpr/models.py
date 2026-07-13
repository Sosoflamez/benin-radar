from django.db import models
from simple_history.models import HistoricalRecords

from apps.detection.models import VehicleDetection


def plate_crop_upload_path(instance: "PlateReading", filename: str) -> str:
    return instance.detection.created_at.strftime("evidence/%Y/%m/%d/plates/") + filename


class PlateReading(models.Model):
    class Status(models.TextChoices):
        LISIBLE = "lisible", "Lisible"
        ILLISIBLE = "plaque_illisible", "Plaque illisible"

    detection = models.ForeignKey(
        VehicleDetection, on_delete=models.CASCADE, related_name="plate_readings"
    )
    raw_plate = models.CharField(max_length=50)
    normalized_plate = models.CharField(max_length=15, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    ocr_confidence = models.DecimalField(max_digits=4, decimal_places=3)
    plate_crop = models.ImageField(upload_to=plate_crop_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("view_plate_data", "Peut consulter les plaques d'immatriculation"),
        ]

    def __str__(self) -> str:
        return self.normalized_plate or f"illisible ({self.detection_id})"
