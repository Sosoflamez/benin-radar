from django.contrib import admin

from apps.detection.models import VehicleDetection


@admin.register(VehicleDetection)
class VehicleDetectionAdmin(admin.ModelAdmin):
    list_display = (
        "camera",
        "track_id",
        "vehicle_class",
        "computed_speed_kmh",
        "tracking_confidence",
        "created_at",
    )
    list_filter = ("camera", "vehicle_class")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in VehicleDetection._meta.fields]

    def has_add_permission(self, request):
        return False
