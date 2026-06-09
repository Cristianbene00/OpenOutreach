"""Log in to LinkedIn once and verify the session is saved.

A focused diagnostic: it does ONLY the login (no task processing), so you can
confirm the browser/checkpoint flow actually persists a session before running
the full daemon. Opens a headed browser — clear any checkpoint by hand in that
window until it reaches the feed.

    venv/bin/python manage.py testlogin            # first active profile
    venv/bin/python manage.py testlogin --handle admin
"""
import logging
import sys

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Log in to LinkedIn once and verify the session cookies are saved."

    def add_arguments(self, parser):
        parser.add_argument("--handle", default=None, help="Django username (default: first active profile)")

    def handle(self, *args, **options):
        from linkedin.logging import configure_logging
        configure_logging(level=logging.INFO)

        from linkedin.browser.registry import get_or_create_session, resolve_profile

        profile = resolve_profile(options["handle"])
        if profile is None:
            self.stderr.write("No active LinkedInProfile found.")
            sys.exit(1)

        logger.info("Logging in as %s …", profile.linkedin_username)
        session = get_or_create_session(profile)

        try:
            session.ensure_browser()  # launches browser, runs login + checkpoint wait
        except Exception:
            logger.exception("Login failed")
            session.close()
            sys.exit(1)

        profile.refresh_from_db()
        has_cookies = bool(profile.cookie_data)
        logger.info("cookies saved: %s | connection_status: %s", has_cookies, profile.connection_status)

        if has_cookies:
            try:
                me = session.self_profile
                name = f"{me.get('first_name', '')} {me.get('last_name', '')}".strip()
                logger.info("✓ Logged in as: %s (%s)", name, me.get("public_identifier"))
                logger.info("Session saved — you can now run `make run`.")
            except Exception:
                logger.exception("Logged in but self-profile fetch failed")
        else:
            logger.error("No cookies saved — login did not complete (checkpoint not cleared?).")

        session.close()
