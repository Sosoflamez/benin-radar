from django.db import models

from apps.cameras.models import Camera


class VehicleDetection(models.Model):
    class VehicleClass(models.TextChoices):
        CAR = "car", "Voiture"
        MOTORCYCLE = "motorcycle", "Moto / Zémidjan"
        BUS = "bus", "Bus"
        TRUCK = "truck", "Camion"

    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="detections")
    track_id = models.PositiveIntegerField()
    vehicle_class = models.CharField(max_length=20, choices=VehicleClass.choices)
    zone_entered_at = models.DateTimeField()
    zone_exited_at = models.DateTimeField()
    computed_speed_kmh = models.DecimalField(max_digits=5, decimal_places=1)
    tracking_confidence = models.DecimalField(max_digits=4, decimal_places=3)
    # Bounding box [x1, y1, x2, y2] au moment du franchissement.
    bbox = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["camera", "track_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.camera.name} · track {self.track_id} · {self.computed_speed_kmh} km/h"
