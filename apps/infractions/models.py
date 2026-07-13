from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.anpr.models import PlateReading
from apps.cameras.models import Camera
from apps.detection.models import VehicleDetection


def evidence_upload_path(instance: "Evidence", filename: str) -> str:
    return instance.infraction.created_at.strftime("evidence/%Y/%m/%d/") + filename


class Infraction(models.Model):
    class Status(models.TextChoices):
        DETECTEE = "detectee", "Détectée"
        VERIFIEE = "verifiee", "Vérifiée"
        VALIDEE = "validee", "Validée"
        REJETEE = "rejetee", "Rejetée"

    detection = models.OneToOneField(
        VehicleDetection, on_delete=models.PROTECT, related_name="infraction"
    )
    camera = models.ForeignKey(Camera, on_delete=models.PROTECT, related_name="infractions")
    plate = models.ForeignKey(
        PlateReading, on_delete=models.PROTECT, related_name="infractions", null=True, blank=True
    )
    recorded_speed_kmh = models.DecimalField(max_digits=5, decimal_places=1)
    speed_limit_kmh = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DETECTEE)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="validated_infractions",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Infraction {self.camera.name} · {self.recorded_speed_kmh} km/h · {self.status}"


class Evidence(models.Model):
    infraction = models.ForeignKey(Infraction, on_delete=models.PROTECT, related_name="evidences")
    full_image = models.ImageField(upload_to=evidence_upload_path)
    plate_crop_image = models.ImageField(upload_to=evidence_upload_path, blank=True)
    sha256_hash = models.CharField(max_length=64, editable=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Preuve infraction #{self.infraction_id} ({self.created_at:%Y-%m-%d})"
