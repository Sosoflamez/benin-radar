from django.urls import path

from apps.dashboard.views import InfractionsLiveView

urlpatterns = [
    path("", InfractionsLiveView.as_view(), name="dashboard-home"),
]
