"""Control center API views. Everything is scoped to ``request.user``."""
from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.models import ChatMessage
from crm.models import Deal
from linkedin.models import (
    ActionLog,
    Campaign,
    LinkedInProfile,
    OutboundMessage,
    SiteConfig,
    Task,
)
from linkedin.onboarding import user_onboarding_status

from .serializers import (
    CampaignSerializer,
    ChatMessageSerializer,
    DealSerializer,
    LLMSettingsSerializer,
    LinkedInProfileSerializer,
    LoginSerializer,
    OutboundMessageSerializer,
    SignupSerializer,
    UserSerializer,
)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

def _me_payload(user) -> dict:
    return {
        "user": UserSerializer(user).data,
        "onboarding": user_onboarding_status(user),
    }


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(_me_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(_me_payload(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(_me_payload(request.user))


# --------------------------------------------------------------------------- #
# LLM settings (singleton SiteConfig)
# --------------------------------------------------------------------------- #

class LLMSettingsView(APIView):
    def get(self, request):
        return Response(LLMSettingsSerializer(SiteConfig.load()).data)

    def put(self, request):
        serializer = LLMSettingsSerializer(
            SiteConfig.load(), data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# --------------------------------------------------------------------------- #
# LinkedIn profile (1:1 with the user)
# --------------------------------------------------------------------------- #

class LinkedInProfileView(APIView):
    def _get_or_none(self, request):
        return LinkedInProfile.objects.filter(user=request.user).first()

    def get(self, request):
        profile = self._get_or_none(request)
        if profile is None:
            return Response({"linkedin_username": "", "connection_status": "not_configured"})
        return Response(LinkedInProfileSerializer(profile).data)

    def put(self, request):
        profile = self._get_or_none(request)
        serializer = LinkedInProfileSerializer(
            profile, data=request.data, partial=profile is not None,
        )
        serializer.is_valid(raise_exception=True)
        if profile is None:
            serializer.save(user=request.user)
        else:
            serializer.save()
        return Response(serializer.data)


# --------------------------------------------------------------------------- #
# Campaigns (ICP) — scoped to the user via the users M2M
# --------------------------------------------------------------------------- #

class CampaignViewSet(viewsets.ModelViewSet):
    serializer_class = CampaignSerializer

    def get_queryset(self):
        return Campaign.objects.filter(users=self.request.user).order_by("name")

    def perform_create(self, serializer):
        campaign = serializer.save()
        campaign.users.add(self.request.user)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        campaign = self.get_object()
        campaign.enabled = True
        campaign.save(update_fields=["enabled"])
        return Response(self.get_serializer(campaign).data)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        campaign = self.get_object()
        campaign.enabled = False
        campaign.save(update_fields=["enabled"])
        return Response(self.get_serializer(campaign).data)


# --------------------------------------------------------------------------- #
# Outbound message queue
# --------------------------------------------------------------------------- #

class QueueViewSet(viewsets.ModelViewSet):
    serializer_class = OutboundMessageSerializer
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        qs = OutboundMessage.objects.filter(
            campaign__users=self.request.user,
        ).select_related("campaign", "lead")
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        campaign_param = self.request.query_params.get("campaign")
        if campaign_param:
            qs = qs.filter(campaign_id=campaign_param)
        return qs

    def _can_edit(self, msg) -> bool:
        return msg.status == OutboundMessage.Status.PENDING_APPROVAL

    def partial_update(self, request, *args, **kwargs):
        msg = self.get_object()
        if not self._can_edit(msg):
            return Response(
                {"detail": "Only pending messages can be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = request.data.get("body")
        if body is not None:
            msg.body = body
            msg.save(update_fields=["body"])
        return Response(self.get_serializer(msg).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        msg = self.get_object()
        if not self._can_edit(msg):
            return Response(
                {"detail": "Only pending messages can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = request.data.get("body")
        if body is not None:
            msg.body = body
        msg.status = OutboundMessage.Status.APPROVED
        msg.decided_at = timezone.now()
        msg.save(update_fields=["body", "status", "decided_at"])
        return Response(self.get_serializer(msg).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        msg = self.get_object()
        if not self._can_edit(msg):
            return Response(
                {"detail": "Only pending messages can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        msg.status = OutboundMessage.Status.REJECTED
        msg.decided_at = timezone.now()
        msg.save(update_fields=["status", "decided_at"])
        return Response(self.get_serializer(msg).data)


# --------------------------------------------------------------------------- #
# Deals + conversations
# --------------------------------------------------------------------------- #

class DealViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DealSerializer

    def get_queryset(self):
        qs = Deal.objects.filter(
            campaign__users=self.request.user,
        ).select_related("lead", "campaign").order_by("-update_date")
        state = self.request.query_params.get("state")
        if state:
            qs = qs.filter(state=state)
        campaign_param = self.request.query_params.get("campaign")
        if campaign_param:
            qs = qs.filter(campaign_id=campaign_param)
        return qs

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        deal = self.get_object()
        ct = ContentType.objects.get_for_model(deal.lead.__class__)
        msgs = ChatMessage.objects.filter(
            content_type=ct, object_id=deal.lead_id,
        ).order_by("creation_date", "pk")
        return Response(ChatMessageSerializer(msgs, many=True).data)


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

class DashboardView(APIView):
    def get(self, request):
        campaigns = Campaign.objects.filter(users=request.user)
        campaign_ids = list(campaigns.values_list("id", flat=True))

        deals_by_state = dict(
            Deal.objects.filter(campaign_id__in=campaign_ids)
            .values_list("state")
            .annotate(n=Count("id"))
        )
        tasks_by_status = dict(
            Task.objects.filter(payload__campaign_id__in=campaign_ids)
            .values_list("status")
            .annotate(n=Count("id"))
        )

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        profile = LinkedInProfile.objects.filter(user=request.user).first()
        actions_today = {"connect": 0, "follow_up": 0}
        limits = {"connect": 0, "follow_up": 0}
        if profile:
            counts = dict(
                ActionLog.objects.filter(
                    linkedin_profile=profile, created_at__gte=today_start,
                )
                .values_list("action_type")
                .annotate(n=Count("id"))
            )
            actions_today = {
                "connect": counts.get("connect", 0),
                "follow_up": counts.get("follow_up", 0),
            }
            limits = {
                "connect": profile.connect_daily_limit,
                "follow_up": profile.follow_up_daily_limit,
            }

        from controlcenter.services import derive_connection_status

        return Response({
            "campaigns": [
                {"id": c.id, "name": c.name, "enabled": c.enabled, "auto_send": c.auto_send}
                for c in campaigns
            ],
            "deals_by_state": deals_by_state,
            "tasks_by_status": tasks_by_status,
            "actions_today": actions_today,
            "daily_limits": limits,
            "pending_approvals": OutboundMessage.objects.filter(
                campaign_id__in=campaign_ids,
                status=OutboundMessage.Status.PENDING_APPROVAL,
            ).count(),
            "linkedin_status": (
                derive_connection_status(profile) if profile else "not_configured"
            ),
            "onboarding": user_onboarding_status(request.user),
        })
