"""Run-control + approve-before-send behavior at the scheduler/handler layer."""
from unittest.mock import patch

import pytest

from linkedin.models import Campaign, OutboundMessage, Task
from linkedin.tasks.scheduler import reconcile


@pytest.mark.django_db
def test_reconcile_skips_disabled_campaign(fake_session):
    """A disabled campaign gets no planned tasks."""
    fake_session.campaign.enabled = False
    fake_session.campaign.save(update_fields=["enabled"])
    reconcile(fake_session)
    assert Task.objects.for_campaigns([fake_session.campaign.pk]).count() == 0


@pytest.mark.django_db
def test_reconcile_plans_enabled_campaign(fake_session):
    fake_session.campaign.enabled = True
    fake_session.campaign.save(update_fields=["enabled"])
    reconcile(fake_session)
    assert Task.objects.for_campaigns([fake_session.campaign.pk]).count() > 0


def _connected_deal(campaign):
    from crm.models import Deal, Lead
    from linkedin_cli.enums import ProfileState

    lead = Lead.objects.create(
        linkedin_url="https://www.linkedin.com/in/target",
        public_identifier="target",
    )
    return Deal.objects.create(lead=lead, campaign=campaign, state=ProfileState.CONNECTED)


@pytest.mark.django_db
def test_follow_up_review_mode_enqueues_without_sending(fake_session):
    """auto_send=False → message goes to the queue, send_raw_message not called."""
    from linkedin.agents.follow_up import FollowUpDecision
    from linkedin.tasks.follow_up import handle_follow_up

    campaign = fake_session.campaign
    campaign.auto_send = False
    campaign.save(update_fields=["auto_send"])
    deal = _connected_deal(campaign)

    decision = FollowUpDecision(action="send_message", message="hey there", follow_up_hours=24)

    with patch("linkedin_cli.actions.message.send_raw_message") as send, \
         patch("linkedin.agents.follow_up.run_follow_up_agent", return_value=decision), \
         patch("linkedin.db.summaries.materialize_profile_summary_if_missing"):
        handle_follow_up(task=None, session=fake_session, qualifiers={})

    send.assert_not_called()
    msg = OutboundMessage.objects.get(deal=deal)
    assert msg.status == OutboundMessage.Status.PENDING_APPROVAL
    assert msg.body == "hey there"
    assert msg.kind == OutboundMessage.Kind.FIRST_TOUCH


@pytest.mark.django_db
def test_follow_up_sends_approved_message(fake_session):
    """An approved queued message is sent on the next slot."""
    from linkedin.tasks.follow_up import handle_follow_up

    campaign = fake_session.campaign
    campaign.auto_send = False
    campaign.save(update_fields=["auto_send"])
    deal = _connected_deal(campaign)
    msg = OutboundMessage.objects.create(
        campaign=campaign, lead=deal.lead, deal=deal,
        kind=OutboundMessage.Kind.FOLLOW_UP, body="approved body",
        status=OutboundMessage.Status.APPROVED,
    )

    with patch("linkedin_cli.actions.message.send_raw_message", return_value=True) as send, \
         patch("linkedin.db.chat.sync_conversation"):
        handle_follow_up(task=None, session=fake_session, qualifiers={})

    send.assert_called_once()
    assert send.call_args[0][2] == "approved body"
    msg.refresh_from_db()
    assert msg.status == OutboundMessage.Status.SENT
