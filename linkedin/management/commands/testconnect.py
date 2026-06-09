"""Send a connection request to one profile — a direct end-to-end connect test.

Bypasses the ML candidate selection (which needs a warmed-up qualifier) and
drives the real connect action against a single profile, recording the result
as a Deal in your CRM. Use it to verify the connect mechanic works once your
LinkedIn session is established (see ``setcookie`` / ``testlogin``).

    venv/bin/python manage.py testconnect --profile https://www.linkedin.com/in/sirojboboev/
    venv/bin/python manage.py testconnect --profile sirojboboev --campaign "Cashera ISO Partnerships"
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send a connection request to one profile (direct connect test)."

    def add_arguments(self, parser):
        parser.add_argument("--profile", required=True, help="LinkedIn profile URL or public identifier")
        parser.add_argument("--handle", default=None, help="Django username (default: first active profile)")
        parser.add_argument("--campaign", default=None, help="Campaign name (default: first non-freemium)")

    def handle(self, *args, **options):
        from linkedin.logging import configure_logging
        configure_logging(level=logging.INFO)

        from linkedin_cli.actions.connect import send_connection_request
        from linkedin_cli.actions.status import get_connection_status
        from linkedin_cli.enums import ProfileState
        from linkedin_cli.url_utils import public_id_to_url, url_to_public_id

        from linkedin.browser.registry import get_or_create_session, resolve_profile
        from linkedin.models import ActionLog, Campaign
        from linkedin.db.deals import set_profile_state
        from crm.models import Deal, Lead

        raw = options["profile"].strip()
        public_id = url_to_public_id(raw) if raw.startswith("http") else raw
        if not public_id:
            self.stderr.write(f"Could not parse a public identifier from {raw!r}")
            return
        url = public_id_to_url(public_id)

        li_profile = resolve_profile(options["handle"])
        if li_profile is None:
            self.stderr.write("No active LinkedInProfile found.")
            return

        if options["campaign"]:
            campaign = Campaign.objects.filter(name=options["campaign"]).first()
        else:
            campaign = (
                Campaign.objects.filter(users=li_profile.user, is_freemium=False).first()
                or Campaign.objects.filter(users=li_profile.user).first()
            )
        if campaign is None:
            self.stderr.write("No campaign found for this user.")
            return

        session = get_or_create_session(li_profile)
        session.campaign = campaign
        session.ensure_browser()

        # Record the target in the CRM so it shows in Deals/dashboard.
        lead, _ = Lead.objects.get_or_create(
            public_identifier=public_id, defaults={"linkedin_url": url},
        )
        Deal.objects.get_or_create(
            lead=lead, campaign=campaign,
            defaults={"state": ProfileState.READY_TO_CONNECT.value},
        )

        profile = {"public_identifier": public_id, "url": url}
        logger.info("Checking connection status for %s …", public_id)
        status = get_connection_status(session, profile)
        logger.info("Current status: %s", status)

        if status in (ProfileState.CONNECTED, ProfileState.PENDING):
            set_profile_state(session, public_id, status.value)
            logger.info("Already %s — nothing to send.", status.value)
            session.close()
            return

        logger.info("Sending connection request to %s …", public_id)
        new_state = send_connection_request(session=session, profile=profile)
        set_profile_state(session, public_id, new_state.value)

        if new_state == ProfileState.PENDING:
            li_profile.record_action(ActionLog.ActionType.CONNECT, campaign)
            logger.info("✓ Connection request SENT to %s (deal → PENDING).", public_id)
        else:
            logger.warning("No connect button / not sent — resulting state: %s", new_state.value)

        session.close()
