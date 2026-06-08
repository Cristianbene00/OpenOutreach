import logging
import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the OpenOutreach daemon (onboard, validate, start task queue)."

    def handle(self, *args, **options):
        self._configure_logging(verbose=options["verbosity"] >= 2)
        self._ensure_db()
        self._ensure_onboarded()

        from linkedin.daemon import run_daemon
        run_daemon()

    # -- Steps ---------------------------------------------------------------

    def _configure_logging(self, verbose: bool = False):
        from linkedin.logging import configure_logging, print_banner

        level = logging.DEBUG if verbose else logging.INFO
        configure_logging(level=level)
        print_banner()

    def _ensure_db(self):
        call_command("migrate", "--no-input")

        from linkedin.management.setup_crm import setup_crm
        setup_crm()

    def _ensure_onboarded(self):
        """Offer the legacy TTY wizard when run interactively with no config.

        In the control-center (web-driven) flow this is a no-op: the daemon
        idles and picks up accounts/campaigns from the DB as users complete
        self-serve onboarding and click Start — so a missing config is no
        longer fatal.
        """
        from linkedin.onboarding import apply, collect_from_wizard, missing_keys

        if not missing_keys():
            return

        if sys.stdin.isatty():
            apply(collect_from_wizard())
        else:
            logger.info(
                "Onboarding incomplete (%s) — idling until configured via the "
                "control center.", ", ".join(sorted(missing_keys())),
            )

    def _ensure_newsletter(self, session):
        if session.linkedin_profile.newsletter_processed:
            return

        from linkedin.api.newsletter import ensure_newsletter_subscription
        from linkedin.setup.gdpr import apply_gdpr_newsletter_override
        from linkedin_cli.url_utils import public_id_to_url

        profile = session.self_profile
        country_code = profile.get("country_code")
        apply_gdpr_newsletter_override(session, country_code)
        linkedin_url = public_id_to_url(profile["public_identifier"])
        ensure_newsletter_subscription(session, linkedin_url=linkedin_url)
        session.linkedin_profile.newsletter_processed = True
        session.linkedin_profile.save(update_fields=["newsletter_processed"])
