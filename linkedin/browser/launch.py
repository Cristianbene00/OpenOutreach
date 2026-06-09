# linkedin/browser/launch.py
"""Persist + orchestrate the daemon's LinkedIn browser session.

Cookie persistence (to the Django DB) and the launch/login orchestration are
OpenOutreach concerns, so they live here. The reusable *mechanics* — launching a
stealthed browser, driving the login form, clearing checkpoints — stay in the
Django-free ``linkedin_cli.browser`` library and are called from here.
"""
from __future__ import annotations

import logging

from playwright.sync_api import Error as PlaywrightError
from termcolor import colored

from linkedin_cli.auth import authenticate
from linkedin_cli.browser.login import dismiss_comply_gate, launch_browser
from linkedin_cli.browser.nav import goto_page
from linkedin_cli.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

LINKEDIN_HOME_URL = "https://www.linkedin.com"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


def _save_cookies(session):
    """Persist Playwright storage state (cookies) to the DB."""
    state = session.context.storage_state()
    session.linkedin_profile.cookie_data = state
    session.linkedin_profile.save(update_fields=["cookie_data"])


def _mark_connected(session):
    """Stamp the control-center connection status after a verified login."""
    from linkedin.models import LinkedInProfile
    from django.utils import timezone

    lp = session.linkedin_profile
    lp.connection_status = LinkedInProfile.ConnectionStatus.CONNECTED
    lp.last_login_error = ""
    lp.last_login_at = timezone.now()
    lp.save(update_fields=["connection_status", "last_login_error", "last_login_at"])


def _restore_saved_session(session):
    """Validate a restored cookie session — resilient to consent-redirect loops.

    Navigating straight to ``/feed/`` with only ``li_at`` can hit
    ``ERR_TOO_MANY_REDIRECTS`` when LinkedIn first wants a consent/locale cookie
    set. So land on the homepage first (which sets those cookies and lets us
    dismiss the consent gate), then go to the feed. A redirect loop on the feed
    means the cookie isn't a clean authenticated session (expired/challenged) —
    surface that as a clear ``AuthenticationError`` instead of a raw Playwright
    traceback.
    """
    page = session.page
    try:
        page.goto(LINKEDIN_HOME_URL, wait_until="domcontentloaded")
    except PlaywrightError as exc:
        logger.warning("Homepage load hiccup (%s) — continuing to feed", exc)
    dismiss_comply_gate(page)

    try:
        page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded")
    except PlaywrightError as exc:
        raise AuthenticationError(
            f"Saved LinkedIn session could not reach the feed ({exc}). "
            "The li_at cookie is likely expired or challenged — re-seed it "
            "(manage.py setcookie) from a fresh browser login."
        ) from exc

    dismiss_comply_gate(page)
    goto_page(
        session,
        action=lambda: None,
        expected_url_pattern="/feed",
        error_message="Saved session invalid",
    )


def start_browser_session(session):
    logger.debug("Configuring browser for %s", session)

    session.linkedin_profile.refresh_from_db(fields=["cookie_data"])
    cookie_data = session.linkedin_profile.cookie_data

    storage_state = cookie_data if cookie_data else None
    if storage_state:
        logger.info("Loading saved session for %s", session)

    session.page, session.context, session.browser, session.playwright = launch_browser(storage_state=storage_state)

    if not storage_state:
        lp = session.linkedin_profile
        authenticate(session, username=lp.linkedin_username, password=lp.linkedin_password)
        logger.info(colored("Login successful", "green", attrs=["bold"]))
    else:
        _restore_saved_session(session)

    # "domcontentloaded" — "load" waits for every subresource (analytics
    # beacons, lazy media) and on LinkedIn that event may never fire,
    # hanging the daemon for the duration of the browser timeout.
    session.page.wait_for_load_state("domcontentloaded")
    # Persist the FULL authenticated storage state (every cookie LinkedIn issued
    # this session — JSESSIONID, bcookie, lidc, …), not just the bare li_at we
    # may have started from. A relaunch from a bare li_at tends to redirect-loop
    # (ERR_TOO_MANY_REDIRECTS); a relaunch from the complete set restores cleanly.
    _save_cookies(session)
    # Login verified (fresh or restored) — clear any prior checkpoint/error so
    # the control center reflects recovery.
    _mark_connected(session)
    logger.info(colored("Browser ready", "green", attrs=["bold"]))
