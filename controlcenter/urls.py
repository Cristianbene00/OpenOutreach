from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CampaignViewSet,
    DashboardView,
    DealViewSet,
    LinkedInProfileView,
    LLMSettingsView,
    LoginView,
    LogoutView,
    MeView,
    QueueViewSet,
    SignupView,
)

router = DefaultRouter(trailing_slash=False)
router.register("campaigns", CampaignViewSet, basename="campaign")
router.register("queue", QueueViewSet, basename="queue")
router.register("deals", DealViewSet, basename="deal")

urlpatterns = [
    path("auth/signup", SignupView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("auth/logout", LogoutView.as_view()),
    path("auth/me", MeView.as_view()),
    path("settings/llm", LLMSettingsView.as_view()),
    path("linkedin", LinkedInProfileView.as_view()),
    path("dashboard", DashboardView.as_view()),
    path("", include(router.urls)),
]
