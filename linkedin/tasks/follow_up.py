# linkedin/tasks/follow_up.py
"""Follow-up task — runs the agentic follow-up for one eligible CONNECTED deal."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from termcolor import colored

from linkedin_cli.enums import ProfileState
from linkedin.models import ActionLog

logger = logging.getLogger(__name__)

# Required silence between nudges scales with unanswered count:
# 1 unanswered → 3d, 2 → 6d, 3 → 9d. Skips the LLM call while open.
MIN_DAYS_PER_UNANSWERED = 3


def _build_send_profile(deal) -> dict:
    """Minimal profile dict for ``send_raw_message`` and its fallbacks."""
    lead = deal.lead
    return {
        "public_identifier": lead.public_identifier,
        "urn": lead.urn or "",
    }


def _too_soon_to_nudge(deal) -> bool:
    """Wait ``unanswered_count * MIN_DAYS_PER_UNANSWERED`` days between nudges."""
    from chat.models import ChatMessage
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(type(deal.lead))
    messages = ChatMessage.objects.filter(content_type=ct, object_id=deal.lead_id)

    last = messages.order_by("-creation_date").first()
    if last is None or not last.is_outgoing:
        return False

    last_reply = messages.filter(is_outgoing=False).order_by("-creation_date").first()
    nudges = messages.filter(is_outgoing=True)
    if last_reply:
        nudges = nudges.filter(creation_date__gt=last_reply.creation_date)

    required = timedelta(days=nudges.count() * MIN_DAYS_PER_UNANSWERED)
    return timezone.now() - last.creation_date < required


def _next_followup_deal(campaign):
    """Oldest CONNECTED deal in *campaign* not on a nudge cooldown."""
    from crm.models import Deal

    deals = (
        Deal.objects.filter(
            campaign=campaign,
            state=ProfileState.CONNECTED,
            outcome="",
            lead__disqualified=False,
        )
        .select_related("lead", "campaign")
        .order_by("update_date")
    )
    for deal in deals:
        if not _too_soon_to_nudge(deal):
            return deal
    return None


def _send_to_deal(session, deal, message: str) -> bool:
    """Send a message to a deal's lead and do the post-send bookkeeping.

    Returns True on success. On send failure the deal is moved back to
    QUALIFIED for re-connection (mirrors the original handler behavior).
    """
    from linkedin_cli.actions.message import send_raw_message
    from linkedin.db.deals import set_profile_state

    public_id = deal.lead.public_identifier
    profile = _build_send_profile(deal)
    sent = send_raw_message(session, profile, message)
    if not sent:
        set_profile_state(session, public_id, ProfileState.QUALIFIED.value)
        logger.warning("follow_up for %s: send failed — moving to QUALIFIED for re-connection", public_id)
        return False
    session.linkedin_profile.record_action(ActionLog.ActionType.FOLLOW_UP, session.campaign)
    # Persist the outgoing message locally and bump update_date so the next
    # slot's eligibility query respects the cooldown and cycles this deal back.
    from linkedin.db.chat import sync_conversation
    try:
        sync_conversation(session, public_id)
    except Exception:
        logger.exception("post-send sync failed for %s (best-effort)", public_id)
    deal.save()
    return True


def _flush_approved(session, campaign) -> bool:
    """Send the oldest manually-approved queued message, if any. Returns True if one was sent."""
    from linkedin.db import outbound

    msg = outbound.next_approved(campaign)
    if msg is None or msg.deal is None:
        return False

    public_id = msg.lead.public_identifier
    logger.info("[%s] %s (approved) %s", campaign, colored("▶ follow_up", "green", attrs=["bold"]), public_id)
    if _send_to_deal(session, msg.deal, msg.body):
        outbound.mark_sent(msg)
    else:
        outbound.mark_failed(msg)
    return True


def handle_follow_up(task, session, qualifiers):
    from linkedin.agents.follow_up import run_follow_up_agent
    from linkedin.db import outbound
    from linkedin.db.deals import set_profile_state
    from linkedin.db.summaries import materialize_profile_summary_if_missing

    campaign = session.campaign

    if not session.linkedin_profile.can_execute(ActionLog.ActionType.FOLLOW_UP):
        logger.info("[%s] follow_up: daily limit reached — slot skipped", campaign)
        return

    # Approve-before-send: drain manually-approved messages first.
    if not campaign.auto_send and _flush_approved(session, campaign):
        return

    deal = _next_followup_deal(campaign)
    if deal is None:
        logger.info("[%s] follow_up: no eligible CONNECTED deal — slot skipped", campaign)
        return

    public_id = deal.lead.public_identifier

    # In review mode, don't re-generate for a deal already awaiting approval.
    if not campaign.auto_send and outbound.has_pending_approval(deal):
        logger.info("[%s] follow_up: %s awaiting approval — slot skipped", campaign, public_id)
        return

    logger.info(
        "[%s] %s %s",
        campaign, colored("▶ follow_up", "green", attrs=["bold"]), public_id,
    )

    materialize_profile_summary_if_missing(deal, session)
    decision = run_follow_up_agent(session, deal)

    if decision.action == "send_message":
        kind = outbound.kind_for(deal)
        if campaign.auto_send:
            logger.info("[%s] follow_up message for %s: %s", campaign, public_id, decision.message)
            if _send_to_deal(session, deal, decision.message):
                outbound.record_sent(deal, decision.message, kind)
        else:
            outbound.enqueue_for_approval(deal, decision.message, kind)
            # Bump update_date so the eligibility query cycles to another deal
            # while this one waits on approval.
            deal.save()

    elif decision.action == "mark_completed":
        set_profile_state(session, public_id, ProfileState.COMPLETED.value, outcome=decision.outcome)
        logger.info("[%s] follow_up completed for %s: outcome=%s", campaign, public_id, decision.outcome)

    elif decision.action == "wait":
        # Bump update_date so the eligibility query cycles to a different deal
        # next time; this deal returns to the front only after others are touched.
        deal.save()
