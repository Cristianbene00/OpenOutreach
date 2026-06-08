"""DRF serializers for the control center API.

Secrets (LinkedIn password, LLM API key) are write-only; reads expose only a
boolean ``*_set`` flag so the SPA can show "configured" without leaking values.
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from chat.models import ChatMessage
from crm.models import Deal
from linkedin.models import Campaign, LinkedInProfile, OutboundMessage, SiteConfig


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        # Control-center accounts are NOT staff (admin) by default and get a
        # real, usable password (unlike the TTY onboarding wizard accounts).
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_staff")


class LLMSettingsSerializer(serializers.ModelSerializer):
    llm_api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    llm_api_key_set = serializers.SerializerMethodField()

    class Meta:
        model = SiteConfig
        fields = ("llm_provider", "ai_model", "llm_api_base", "llm_api_key", "llm_api_key_set")

    def get_llm_api_key_set(self, obj) -> bool:
        return bool(obj.llm_api_key)

    def update(self, instance, validated_data):
        # Don't wipe a stored key when the client omits it (or sends blank).
        if not validated_data.get("llm_api_key"):
            validated_data.pop("llm_api_key", None)
        return super().update(instance, validated_data)


class LinkedInProfileSerializer(serializers.ModelSerializer):
    linkedin_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    linkedin_password_set = serializers.SerializerMethodField()
    connection_status = serializers.SerializerMethodField()

    class Meta:
        model = LinkedInProfile
        fields = (
            "linkedin_username", "linkedin_password", "linkedin_password_set",
            "active", "connect_daily_limit", "follow_up_daily_limit",
            "subscribe_newsletter", "connection_status", "last_login_error",
            "last_login_at",
        )
        read_only_fields = ("last_login_error", "last_login_at")

    def get_linkedin_password_set(self, obj) -> bool:
        return bool(obj.linkedin_password)

    def get_connection_status(self, obj) -> str:
        from controlcenter.services import derive_connection_status
        return derive_connection_status(obj)

    def update(self, instance, validated_data):
        if not validated_data.get("linkedin_password"):
            validated_data.pop("linkedin_password", None)
        return super().update(instance, validated_data)


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = (
            "id", "name", "product_docs", "campaign_objective", "booking_link",
            "seed_public_ids", "action_fraction", "is_freemium", "enabled",
            "auto_send", "connection_note_template", "follow_up_template",
        )
        read_only_fields = ("is_freemium",)


class OutboundMessageSerializer(serializers.ModelSerializer):
    lead_name = serializers.SerializerMethodField()
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    class Meta:
        model = OutboundMessage
        fields = (
            "id", "campaign", "campaign_name", "lead", "lead_name", "deal",
            "kind", "status", "body", "created_at", "decided_at", "sent_at",
        )
        read_only_fields = (
            "campaign", "lead", "deal", "kind", "created_at", "decided_at",
            "sent_at", "status",
        )

    def get_lead_name(self, obj) -> str:
        return obj.lead.public_identifier if obj.lead_id else ""


class DealSerializer(serializers.ModelSerializer):
    public_identifier = serializers.CharField(source="lead.public_identifier", read_only=True)
    linkedin_url = serializers.CharField(source="lead.linkedin_url", read_only=True)
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    class Meta:
        model = Deal
        fields = (
            "id", "public_identifier", "linkedin_url", "campaign", "campaign_name",
            "state", "outcome", "reason", "creation_date", "update_date",
        )


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ("id", "content", "is_outgoing", "creation_date")
