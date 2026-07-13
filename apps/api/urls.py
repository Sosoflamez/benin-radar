from rest_framework.routers import DefaultRouter

from apps.api.views import EvidenceViewSet, InfractionViewSet

router = DefaultRouter()
router.register("infractions", InfractionViewSet, basename="infraction")
router.register("evidences", EvidenceViewSet, basename="evidence")

urlpatterns = router.urls
