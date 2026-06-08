# linkedin/daemon.py
from __future__ import annotations

import logging
import random
import sys
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from pydantic_ai.exceptions import ModelHTTPError

from termcolor import colored

from linkedin.conf import (
    ACTIVE_END_HOUR,
    ACTIVE_START_HOUR,
    ACTIVE_TIMEZONE,
    CAMPAIGN_CONFIG,
    ENABLE_ACTIVE_HOURS,
)
from linkedin.diagnostics import failure_diagnostics
from linkedin_cli.exceptions import AuthenticationError, CheckpointChallengeError
from linkedin.ml.qualifier import BayesianQualifier, KitQualifier
from linkedin.models import Task
from linkedin.tasks.check_pending import handle_check_pending
from linkedin.tasks.connect import handle_connect
from linkedin.tasks.follow_up import handle_follow_up

logger = logging.getLogger(__name__)

_HANDLERS = {
    Task.TaskType.CONNECT: handle_connect,
    Task.TaskType.CHECK_PENDING: handle_check_pending,
    Task.TaskType.FOLLOW_UP: handle_follow_up,
}

HEARTBEAT_INTERVAL = 300  # 5 minutes
HEARTBEAT_SLICE = 60      # wake every minute during long sleeps


# ── Cloud promo ──────────────────────────────────────────────────────

_CLOUD_MESSAGES = [
    "Tired of keeping your laptop open? Run your pipeline in the cloud for $49/mo",
    "You already trust the engine. Now let it run without you babysitting your laptop",
    "The AI gets smarter with every lead. Let it run 24/7 on Cloud instead of only when your laptop is open",
    "Miss a day and the pipeline stalls — follow-ups go cold, new candidates don't get discovered. Cloud keeps it running",
    "The tool got good enough that running it locally became a job. Cloud fixes that",
    "\u2601  OpenOutreach Cloud: same AI, same code, zero ops. One command and you're live",
    "\U0001f9e0 Your AI sales team, running in the cloud. $49/mo",
    "Smart founders shouldn't be acting like robots. Let the AI handle outreach while you build your product",
    "Your leads are compounding. Your laptop shouldn't be the bottleneck",
    "\u26a1 Competitors charge $50-100/mo for template bots. Cloud gives you autonomous AI discovery for $49/mo",
    "Other tools need you to build or buy contact lists. OpenOutreach discovers leads autonomously — describe your market and the AI does the rest",
    "Expandi and Waalaxy send templates. OpenOutreach's AI agent reads conversation history and writes personalized follow-ups",
    "Running Docker + VPN yourself? Cloud handles everything — dedicated server, VPN included",
    "Self-hosted setup: 30-60 min. Cloud setup: ~1 min. Same AI, same results",
    "The server costs ~$18/mo. The VPN costs ~$6/mo. You're paying $25/mo for managed ops — if your time is worth more, Cloud pays for itself",
    "Your data never leaves your machine. Cloud is just a disposable execution layer. $49/mo, cancel anytime",
    "mTLS encryption between your machine and the server. The control plane never sees your data",
    "100% open source. Inspect every line of code on GitHub. Cloud runs the exact same codebase — no black box, no lock-in",
    "Switch between self-hosted and Cloud with one command. Download your db.sqlite3 anytime — zero lock-in",
    "No annual commitment. No usage caps. No feature gating. $49/mo, cancel anytime",
    "openoutreach logs — stream live output from your cloud instance. Watch every lead, every message, every decision in real time",
    "openoutreach down saves your DB locally and destroys the server. No orphaned servers, no forgotten bills",
]

_CLOUD_COLORS = ["cyan", "green", "yellow", "magenta"]

_CLOUD_CTAS = [
    "curl -fsSL https://openoutreach.app/install | sh",
    "curl -fsSL https://openoutreach.app/install | sh && openoutreach signup",
    "https://openoutreach.app",
]


class _CloudPromoRotator:
    """Logs a Cloud promo message at most once every *interval* seconds."""

    def __init__(self, interval: float = 120):
        self._interval = interval
        self._last = 0.0

    def maybe_log(self):
        now = time.monotonic()
        if now - self._last < self._interval:
            return
        self._last = now
        msg = random.choice(_CLOUD_MESSAGES)
        color = random.choice(_CLOUD_COLORS)
        cta = random.choice(_CLOUD_CTAS)
        logger.info(
            colored(msg + " \u2192 ", color, attrs=["bold"])
            + colored(cta, "white", attrs=["bold"]),
        )


# ── Heartbeat ────────────────────────────────────────────────────────


class Heartbeat:
    """Logs an ``alive — <context>`` line at most once every *interval* seconds.

    The first call won't log (``_last`` starts at now) — quiet gaps begin
    counting from daemon start, not the Unix epoch.
    """

    def __init__(self, interval: float = HEARTBEAT_INTERVAL):
        self._interval = interval
        self._last = time.monotonic()

    def maybe_log(self, context: str) -> None:
        now = time.monotonic()
        if now - self._last < self._interval:
            return
        self._last = now
        logger.info(colored("alive", "cyan") + " — %s", context)


def sleep_with_heartbeat(seconds: float, heartbeat: Heartbeat, context: str) -> None:
    """``time.sleep(seconds)`` that wakes every ``HEARTBEAT_SLICE`` seconds to
    let *heartbeat* fire. Use for any idle sleep longer than the heartbeat
    interval so the daemon never goes silent for more than 5 minutes.
    """
    end = time.monotonic() + seconds
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(HEARTBEAT_SLICE, remaining))
        heartbeat.maybe_log(context)


# ── Human-rhythm pacing ──────────────────────────────────────────────


class _HumanRhythmBreak:
    """Wall-clock burst timer that injects a random break between bursts.

    Call ``reset()`` after idle sleeps (active-hours pause, waiting for
    the next scheduled task) so the burst timer tracks real work, not
    wall-clock. Call ``maybe_break()`` after each successful task —
    it sleeps a random break duration when the current burst is done.
    """

    def __init__(self, heartbeat: Heartbeat):
        self._heartbeat = heartbeat
        self._new_burst()

    def _new_burst(self):
        self._burst_start = time.monotonic()
        self._burst_duration = random.uniform(
            CAMPAIGN_CONFIG["burst_min_seconds"],
            CAMPAIGN_CONFIG["burst_max_seconds"],
        )

    def reset(self):
        """Start a fresh burst without taking a break. Use after idle gaps."""
        self._new_burst()

    def maybe_break(self):
        """Sleep a random break and start a new burst if the current one is done."""
        if time.monotonic() - self._burst_start < self._burst_duration:
            return
        break_seconds = random.uniform(
            CAMPAIGN_CONFIG["break_min_seconds"],
            CAMPAIGN_CONFIG["break_max_seconds"],
        )
        logger.info("Taking a %dm break", int(break_seconds // 60))
        sleep_with_heartbeat(
            break_seconds,
            self._heartbeat,
            f"on break, {int(break_seconds // 60)}m total",
        )
        self._new_burst()


def _build_qualifiers(campaigns, cfg, kit_model=None):
    """Create a qualifier for every campaign, keyed by campaign PK."""
    from crm.models import Lead

    qualifiers: dict[int, BayesianQualifier | KitQualifier] = {}
    n_regular = 0
    for campaign in campaigns:
        if campaign.is_freemium:
            if kit_model is None:
                continue
            qualifiers[campaign.pk] = KitQualifier(kit_model)
        else:
            q = BayesianQualifier(
                seed=42,
                n_mc_samples=cfg["qualification_n_mc_samples"],
                campaign=campaign,
            )
            X, y = Lead.get_labeled_arrays(campaign)
            if len(X) > 0:
                q.warm_start(X, y)
                logger.info(
                    colored("GP qualifier warm-started", "cyan")
                    + " on %d labelled samples (%d positive, %d negative)"
                    + " for campaign %s",
                    len(y), int((y == 1).sum()), int((y == 0).sum()), campaign,
                )
            qualifiers[campaign.pk] = q
            n_regular += 1

    return qualifiers


# ------------------------------------------------------------------
# Active-hours schedule guard
# ------------------------------------------------------------------


def seconds_until_active() -> float:
    """Return seconds to wait before the next active window, or 0 if active now.

    Single contiguous daily window — no weekend skip.
    """
    if not ENABLE_ACTIVE_HOURS:
        return 0.0
    tz = ZoneInfo(ACTIVE_TIMEZONE)
    now = timezone.localtime(timezone=tz)

    if ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR:
        return 0.0

    candidate = timezone.make_aware(
        now.replace(hour=ACTIVE_START_HOUR, minute=0, second=0, microsecond=0, tzinfo=None),
        timezone=tz,
    )
    if candidate <= now:
        candidate += timedelta(days=1)
    return (candidate - now).total_seconds()


# ------------------------------------------------------------------
# Checkpoint exit
# ------------------------------------------------------------------


def _exit_on_checkpoint(session, task, url: str) -> None:
    """Log loudly, mark the task failed, close the session, and exit(1).

    Called when LinkedIn flags the account with a security checkpoint.
    We do NOT retry or reauthenticate — every retry hardens the block.
    The user clears the challenge in a real browser, then restarts the daemon.
    """
    logger.error(
        colored(
            f"ACCOUNT CHECKPOINTED — {session.linkedin_profile.linkedin_username}",
            "red", attrs=["bold"],
        )
    )
    logger.error("Clear the challenge in a real browser: %s", url)
    logger.error("Then restart the daemon.")
    # Surface the state to the control center before halting.
    from linkedin.models import LinkedInProfile
    profile = session.linkedin_profile
    profile.connection_status = LinkedInProfile.ConnectionStatus.CHECKPOINT
    profile.last_login_error = f"Security checkpoint: {url}"
    profile.save(update_fields=["connection_status", "last_login_error"])
    task.mark_failed()
    session.close()
    sys.exit(1)


# ------------------------------------------------------------------
# Task queue worker
# ------------------------------------------------------------------


class _ProfileWorker:
    """Per-LinkedIn-account state: a browser session + lazily-built qualifiers.

    The browser is only launched when there's an actual task to run (claiming
    and planning are DB-only), so unconfigured/idle accounts cost nothing.
    """

    def __init__(self, session, kit):
        self.session = session
        self._kit = kit
        self._qualifiers = None
        self._freemium_seeded = False

    def active_campaign_ids(self) -> list[int]:
        """Enabled (or freemium) campaign ids for this account, fresh each cycle."""
        # campaigns is a cached_property — drop it so newly created/enabled
        # campaigns appear without a daemon restart.
        self.session.__dict__.pop("campaigns", None)
        return [
            c.pk for c in self.session.campaigns
            if c.enabled or c.is_freemium
        ]

    def ensure_ready(self):
        """Launch the browser, build qualifiers, seed freemium — once."""
        self.session.ensure_browser()
        if self._qualifiers is None:
            self._qualifiers = _build_qualifiers(
                self.session.campaigns, CAMPAIGN_CONFIG,
                kit_model=self._kit["model"] if self._kit else None,
            )
        if self._kit and not self._freemium_seeded:
            self._seed_freemium()
            self._freemium_seeded = True

    @property
    def qualifiers(self):
        return self._qualifiers or {}

    def _seed_freemium(self):
        from linkedin.setup.freemium import import_freemium_campaign, seed_profiles

        freemium_campaign = import_freemium_campaign(self._kit["config"])
        if not freemium_campaign:
            return
        prev = getattr(self.session, "campaign", None)
        self.session.campaign = freemium_campaign
        try:
            seed_profiles(self.session, self._kit["config"])
        finally:
            self.session.campaign = prev


def _dispatch(task, session, qualifiers) -> str:
    """Run one task. Returns 'ok' | 'failed' | 'stop' (LLM error → halt account)."""
    from linkedin.models import Campaign

    campaign = Campaign.objects.filter(pk=task.payload.get("campaign_id")).first()
    if not campaign:
        logger.error("Campaign %s not found", task.payload.get("campaign_id"))
        task.mark_failed()
        return "failed"

    session.campaign = campaign
    task.mark_running()

    handler = _HANDLERS.get(task.task_type)
    if handler is None:
        logger.error("Unknown task type: %s", task.task_type)
        task.mark_failed()
        return "failed"

    try:
        with failure_diagnostics(session):
            handler(task, session, qualifiers)
    except CheckpointChallengeError as exc:
        _exit_on_checkpoint(session, task, exc.url)
    except AuthenticationError:
        logger.warning("Session expired during %s — re-authenticating", task)
        try:
            session.reauthenticate()
        except CheckpointChallengeError as exc:
            _exit_on_checkpoint(session, task, exc.url)
        except Exception:
            logger.exception("Re-authentication failed for %s", task)
        task.mark_failed()
        return "failed"
    except ModelHTTPError as e:
        task.mark_failed()
        logger.error(
            colored("Account paused — LLM API error", "red", attrs=["bold"])
            + "\n%s\nCheck llm_provider, ai_model, llm_api_key, and llm_api_base in Site Configuration.", e,
        )
        return "stop"
    except Exception:
        task.mark_failed()
        logger.exception("Task %s failed", task)
        return "failed"

    task.mark_completed()
    return "ok"


def run_daemon():
    """Multi-account task-queue worker.

    Each cycle round-robins over every active LinkedIn account, running at most
    one task per account before moving on (one headed browser at a time — running
    many concurrently is too heavy for the self-host target). Accounts/campaigns
    are picked up live from the DB as users finish self-serve onboarding and click
    Start, so the daemon never needs a restart for config changes.
    """
    from linkedin.ml.hub import fetch_kit
    from linkedin.models import LinkedInProfile
    from linkedin.browser.registry import get_or_create_session
    from linkedin.tasks.scheduler import reconcile

    kit = fetch_kit()  # shared freemium model, loaded once

    logger.info(colored("Daemon started", "green", attrs=["bold"]) + " — multi-account task queue worker")

    heartbeat = Heartbeat()
    rhythm = _HumanRhythmBreak(heartbeat)
    workers: dict[int, _ProfileWorker] = {}

    while True:
        pause = seconds_until_active()
        if pause > 0:
            h, m = int(pause // 3600), int(pause % 3600 // 60)
            logger.info("Outside active hours — sleeping %dh%02dm", h, m)
            sleep_with_heartbeat(pause, heartbeat, f"outside active hours, {h}h{m:02d}m left")
            rhythm.reset()
            continue

        profiles = list(LinkedInProfile.objects.filter(active=True).select_related("user"))
        if not profiles:
            sleep_with_heartbeat(3600, heartbeat, "no active accounts")
            rhythm.reset()
            continue

        did_work = False
        next_waits: list[float] = []

        for profile in profiles:
            worker = workers.get(profile.pk)
            if worker is None:
                worker = _ProfileWorker(get_or_create_session(profile), kit)
                workers[profile.pk] = worker

            campaign_ids = worker.active_campaign_ids()
            if not campaign_ids:
                continue  # nothing enabled for this account

            task = Task.objects.claim_next_for(campaign_ids)
            if task is None:
                # DB-only planning — no browser needed.
                reconcile(worker.session)
                wait = Task.objects.seconds_to_next(campaign_ids)
                if wait is not None:
                    next_waits.append(wait)
                continue

            worker.ensure_ready()  # launch browser only now that there's work
            result = _dispatch(task, worker.session, worker.qualifiers)
            if result == "stop":
                # Skip this account for the rest of the cycle; other accounts run.
                continue
            did_work = True
            rhythm.maybe_break()

        if not did_work:
            wait = min(next_waits) if next_waits else 3600
            wait = max(wait, 1)
            h, m = int(wait // 3600), int(wait % 3600 // 60)
            logger.info("No ready tasks — sleeping %dh%02dm", h, m)
            sleep_with_heartbeat(wait, heartbeat, f"idle, next in {h}h{m:02d}m")
            rhythm.reset()
