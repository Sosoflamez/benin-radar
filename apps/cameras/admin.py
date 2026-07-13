from django.contrib import admin

from apps.cameras.models import CalibrationProfile, Camera


class CalibrationProfileInline(admin.StackedInline):
    model = CalibrationProfile
    extra = 0


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("name", "speed_limit_kmh", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [CalibrationProfileInline]
