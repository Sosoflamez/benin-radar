from django.db import models


class Camera(models.Model):
    name = models.CharField(max_length=100, unique=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    stream_url = models.CharField(max_length=500)
    speed_limit_kmh = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CalibrationProfile(models.Model):
    camera = models.OneToOneField(
        Camera, on_delete=models.CASCADE, related_name="calibration_profile"
    )
    # Matrice d'homographie 3x3 (image -> plan monde), sérialisée en JSON.
    homography_matrix = models.JSONField()
    # Points de référence utilisés pour le calcul de l'homographie.
    reference_points = models.JSONField()
    measured_distance_m = models.DecimalField(max_digits=6, decimal_places=2)
    calibrated_at = models.DateTimeField()

    class Meta:
        ordering = ["-calibrated_at"]

    def __str__(self) -> str:
        return f"Calibration {self.camera.name} ({self.calibrated_at:%Y-%m-%d})"
