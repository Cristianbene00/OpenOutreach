"""Pure helpers for the control center API — no browser/Playwright imports.

The web process must never launch a browser, so connection status is derived
purely from DB state (saved cookies + the daemon-stamped status field).
"""
from __future__ import annotations

import time

_AUTH_COOKIE_NAME = "li_at"


def derive_connection_status(profile) -> str:
    """Best-effort LinkedIn link status from saved cookies + stamped status.

    Mirrors the ``li_at`` expiry check in ``browser/session.py`` without
    importing the browser layer. Returns one of the
    ``LinkedInProfile.ConnectionStatus`` values.
    """
    from linkedin.models import LinkedInProfile

    Status = LinkedInProfile.ConnectionStatus

    # Daemon-reported terminal states win — only it can observe these.
    if profile.connection_status in (Status.CHECKPOINT, Status.ERROR):
        return profile.connection_status

    if not profile.linkedin_username or not profile.linkedin_password:
        return Status.NOT_CONFIGURED

    cookie_data = profile.cookie_data
    if not cookie_data:
        return Status.PENDING_LOGIN

    for cookie in cookie_data.get("cookies", []):
        if cookie.get("name") == _AUTH_COOKIE_NAME:
            expires = cookie.get("expires", -1)
            if expires > 0 and expires < time.time():
                return Status.EXPIRED
            return Status.CONNECTED

    # Cookies present but no auth cookie — treat as pending.
    return Status.PENDING_LOGIN
