"""Seed a LinkedIn session from a browser cookie (bypass the scripted login).

LinkedIn frequently blocks automated logins from new environments/IPs
(``errorKey=auth_context_expired``). The robust workaround for self-hosted use
is to log in normally in your own browser, copy the ``li_at`` session cookie,
and store it here — the daemon then loads that session and skips the login form
entirely.

Get ``li_at`` from your browser while logged into LinkedIn:
  DevTools → Application/Storage → Cookies → https://www.linkedin.com → ``li_at``
(optionally also ``JSESSIONID``).

    venv/bin/python manage.py setcookie --li-at "AQED..." [--jsessionid "ajax:123"] [--handle admin]
"""
import logging
import time

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

_ONE_YEAR = 365 * 24 * 3600


class Command(BaseCommand):
    help = "Seed a LinkedIn session from a browser li_at cookie (skip scripted login)."

    def add_arguments(self, parser):
        parser.add_argument("--li-at", required=True, help="li_at cookie value from your browser")
        parser.add_argument("--jsessionid", default=None, help="JSESSIONID cookie value (optional)")
        parser.add_argument("--handle", default=None, help="Django username (default: first active profile)")

    def handle(self, *args, **options):
        from linkedin.logging import configure_logging
        configure_logging(level=logging.INFO)

        from linkedin.browser.registry import resolve_profile
        from linkedin.models import LinkedInProfile

        profile = resolve_profile(options["handle"])
        if profile is None:
            self.stderr.write("No active LinkedInProfile found.")
            return

        expires = int(time.time()) + _ONE_YEAR
        cookies = [{
            "name": "li_at",
            "value": options["li_at"].strip().strip('"'),
            "domain": ".linkedin.com",
            "path": "/",
            "expires": expires,
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        }]
        if options["jsessionid"]:
            cookies.append({
                "name": "JSESSIONID",
                "value": options["jsessionid"].strip().strip('"'),
                "domain": ".linkedin.com",
                "path": "/",
                "expires": expires,
                "httpOnly": False,
                "secure": True,
                "sameSite": "None",
            })

        profile.cookie_data = {"cookies": cookies, "origins": []}
        profile.connection_status = LinkedInProfile.ConnectionStatus.CONNECTED
        profile.last_login_error = ""
        profile.save(update_fields=["cookie_data", "connection_status", "last_login_error"])

        logger.info(
            "Saved session cookie for %s (%s). Run `venv/bin/python manage.py testlogin` "
            "to verify, then `make run`.",
            profile.user.username, profile.linkedin_username,
        )
