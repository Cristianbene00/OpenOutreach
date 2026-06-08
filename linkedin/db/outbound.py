"""Outbound message queue helpers — the bridge between the follow-up handler
and the control center's reviewable queue (``OutboundMessage``).

When ``Campaign.auto_send`` is True the daemon sends immediately and logs a
``SENT`` row for the activity view. When False, the daemon enqueues a
``PENDING_APPROVAL`` row instead of sending; the control center approves/edits
it, and a later slot picks up the ``APPROVED`` row and sends it.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from linkedin.models import OutboundMessage

logger = logging.getLogger(__name__)


def has_outgoing_message(lead) -> bool:
    """True if we've ever sent this lead a message (→ follow_up, not first_touch)."""
    from chat.models import ChatMessage
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(lead.__class__)
    return ChatMessage.objects.filter(
        content_type=ct, object_id=lead.pk, is_outgoing=True,
    ).exists()


def kind_for(deal) -> str:
    """First message to a lead is a first_touch; later ones are follow_ups."""
    return (
        OutboundMessage.Kind.FOLLOW_UP
        if has_outgoing_message(deal.lead)
        else OutboundMessage.Kind.FIRST_TOUCH
    )


def has_pending_approval(deal) -> bool:
    return OutboundMessage.objects.filter(
        deal=deal, status=OutboundMessage.Status.PENDING_APPROVAL,
    ).exists()


def enqueue_for_approval(deal, body: str, kind: str) -> OutboundMessage:
    """Stage a generated message for manual approval (auto_send=False path)."""
    msg = OutboundMessage.objects.create(
        campaign=deal.campaign, lead=deal.lead, deal=deal,
        kind=kind, body=body, status=OutboundMessage.Status.PENDING_APPROVAL,
    )
    logger.info("Queued %s for approval → %s", kind, deal.lead.public_identifier)
    return msg


def record_sent(deal, body: str, kind: str) -> OutboundMessage:
    """Log an already-sent message so it shows in the queue/activity view."""
    return OutboundMessage.objects.create(
        campaign=deal.campaign, lead=deal.lead, deal=deal,
        kind=kind, body=body, status=OutboundMessage.Status.SENT,
        decided_at=timezone.now(), sent_at=timezone.now(),
    )


def next_approved(campaign) -> OutboundMessage | None:
    """Oldest approved-but-unsent message for the campaign."""
    return (
        OutboundMessage.objects.filter(
            campaign=campaign, status=OutboundMessage.Status.APPROVED,
        )
        .select_related("deal", "lead")
        .order_by("created_at")
        .first()
    )


def mark_sent(msg: OutboundMessage) -> None:
    msg.status = OutboundMessage.Status.SENT
    msg.sent_at = timezone.now()
    msg.save(update_fields=["status", "sent_at"])


def mark_failed(msg: OutboundMessage) -> None:
    msg.status = OutboundMessage.Status.FAILED
    msg.save(update_fields=["status"])
