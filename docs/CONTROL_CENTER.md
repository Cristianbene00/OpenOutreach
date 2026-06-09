# Control Center — Runbook & Handoff

The self-serve, multi-user web UI that replaces Django-Admin-only operation. This
doc is the single place to pick up work: it covers how to run/test everything,
the LinkedIn-session gotchas, the prospecting pipeline, and **where we currently
left off**. For deep module docs see [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
for rules/quick-ref see [`../CLAUDE.md`](../CLAUDE.md).

---

## 🧭 Current status & next steps

**Branch state:** everything is merged to `main` and pushed to
`github.com/Cristianbene00/OpenOutreach` (latest commit: cold-start connect fix).

**What works (verified):**
- Control center web app: signup/login, onboarding, campaigns/ICP, settings, queue, deals, dashboard. Per-user scoping confirmed.
- Daemon boots into the multi-account loop and plans/reconciles tasks for enabled campaigns.
- LinkedIn login **via session cookie** (`setcookie` → `testlogin` reached the feed as the real account).
- Cold-start connect fix merged: a fresh campaign now promotes LLM-qualified leads and selects READY leads even before the GP model warms up (previously it stalled forever).

**Current DB state (single operator):**
- User `admin` (the superuser; control-center + admin login).
- LinkedIn profile: `cristianbene0@gmail.com`, `connection_status=connected` (cookie may be stale — re-seed if needed).
- LLM: Anthropic `claude-3-5-haiku-20241022`, key set.
- Campaign **`Cashera ISO Partnerships`** — `enabled=True`, regular (non-freemium), good objective + product docs.
- `Freemium Outreach` — disabled (the empty kit campaign; ignore).
- **`sirojboboev` is seeded as `READY_TO_CONNECT`** on Cashera as a deterministic connect test target.

**⏭️ Next step — verify the first real connection (on a residential network):**
1. Grab a **fresh `li_at`** from a browser logged into LinkedIn (DevTools → Application → Cookies → `https://www.linkedin.com` → `li_at`).
2. `venv/bin/python manage.py setcookie --li-at "FRESH" --handle admin`
3. `make run` and **leave it running** (do NOT run repeated `testconnect`/`testlogin` — relaunching browsers in bursts is what trips LinkedIn's anti-automation).
4. On the first connect slot it should pick up `sirojboboev` → `▶ connect` in the log → deal → `PENDING`. Confirm on LinkedIn under *My Network → Sent*.
5. Then it runs autonomously (search → qualify → promote → connect from the Cashera objective).

**Known caveats / open items:**
- LinkedIn **scripted login is blocked** (`errorKey=auth_context_expired`) — we use the `setcookie` cookie path instead. A fresh `li_at` lasts a while; re-seed when login starts failing.
- Earlier testing was on a VM/IP that LinkedIn flagged (it killed each `li_at` after ~one use). Residential IP is the real fix.
- 🔐 A GitHub PAT and a `li_at` were pasted into chat during setup — **rotate/revoke them.** Consider SSH for pushes (`origin` is HTTPS).
- `feature/control-center-ui` branch still exists on GitHub (fully merged; safe to delete).

---

## 🚀 Quick start

Two processes share `data/db.sqlite3` — run them in separate terminals. (Use
`venv/bin/python`; the repo's virtualenv is `venv/`, not `.venv/`.)

```bash
# One-time
make frontend-install        # npm install in frontend/
make frontend-build          # build SPA → frontend/dist (served by Django)

# Terminal 1 — web (control center + API + admin)
make web                     # http://localhost:8000/   (admin at /admin/)

# Terminal 2 — daemon (does the LinkedIn work)
make run
```

- `make frontend-dev` runs the Vite dev server with hot reload (proxies `/api` → :8000).
- Docker: `make up` starts both `app` (daemon, Xvfb/VNC) and `web` (port 8000) services.
- Control-center login uses the `admin` superuser password (`venv/bin/python manage.py changepassword admin` if forgotten).

---

## 🏗️ Architecture (brief)

```
React SPA (Vite/TS/Tailwind, frontend/)  ──fetch + session cookie + CSRF──►  DRF API (/api/*)
        served by Django (index.html template + /static assets)                    │
                                       data/db.sqlite3  ◄── reconcile()/handlers ── rundaemon (worker, owns browser)
```

- **Web ↔ daemon are decoupled** — the UI only writes DB rows; the daemon reacts on its next loop. No IPC.
- **Auth:** DRF `SessionAuthentication` + CSRF. The SPA reads the `csrftoken` cookie (set by the `@ensure_csrf_cookie` shell view in `linkedin/urls.py`) and sends `X-CSRFToken`. Everything scoped to `request.user`.
- **New Django app:** `controlcenter/` (`views.py`, `serializers.py`, `urls.py`, `services.py`) — API only, no models.

### API endpoints (`/api/...`, no trailing slash)
`auth/{signup,login,logout,me}` · `settings/llm` · `linkedin` (+ derived `connection_status`) · `campaigns` (+ `{id}/start`, `{id}/stop`) · `queue` (+ `{id}/approve`, `{id}/reject`, PATCH edit) · `deals` (+ `{id}/messages`) · `dashboard`. Secrets are write-only (`*_set` booleans on read).

### SPA pages (`frontend/src/pages/`)
`Login`, `Signup`, `Onboarding` (checklist), `Dashboard` (funnel + daily-limit usage + LinkedIn status), `Campaigns` + `CampaignEditor` (ICP + templates + auto_send + Start/Stop), `Queue` (approve/edit/reject), `Deals` (+ conversation drawer), `LinkedIn` (credentials + status), `Settings` (LLM).

### Key model additions
- `Campaign`: `enabled` (run flag — daemon only prospects enabled campaigns), `auto_send` (False ⇒ queue messages for approval), `connection_note_template` / `follow_up_template` (seed the AI follow-up agent).
- `OutboundMessage` (`linkedin` app): the reviewable message queue — `kind` (first_touch/follow_up), `status` (pending_approval/approved/sent/rejected/failed), `body`. Written by `tasks/follow_up.py` via `linkedin/db/outbound.py`.
- `LinkedInProfile`: `connection_status`, `last_login_error`, `last_login_at` (surfaced to the UI).

---

## 🔧 Management commands

| Command | Purpose |
|---|---|
| `rundaemon` | The worker loop (multi-account). `make run`. |
| `setcookie --li-at "<value>" [--jsessionid "<v>"] [--handle admin]` | Seed a LinkedIn session from a browser `li_at` cookie — **bypasses the blocked scripted login.** |
| `testlogin [--handle admin]` | Log in once and verify the session saves (no task processing). Opens a headed browser. |
| `testconnect --profile <url-or-id> [--campaign "<name>"]` | Send a connection request to one profile directly (bypasses ML selection). Records a Deal. **Relaunches a browser each call — don't run in bursts.** |
| `setup_crm` / `migrate` | DB bootstrap. |

---

## 🔑 LinkedIn session & login (the operational reality)

LinkedIn actively resists automated logins. Practical model:

1. **Scripted login (username/password) is usually blocked** → `errorKey=auth_context_expired`, redirect to `/flagship-web/login/`. Don't hammer it (each retry hardens the block).
2. **Use the cookie path instead:** log into LinkedIn in a normal browser, copy the `li_at` cookie, and `setcookie` it. The daemon loads that session and skips the login form. **This is the supported way to authenticate self-hosted.**
3. **Checkpoints** (security challenges) must be cleared by a human **in the daemon's own headed browser window** (a "Chrome for Testing" window on the desktop; or noVNC at `localhost:6080` in Docker). Approving on the phone alone often doesn't advance that window.
4. **Session resilience** (`linkedin/browser/launch.py`): restore navigates the homepage first (avoids consent-redirect loops), then saves the **full** cookie set so relaunches don't fall back to a bare `li_at` (which LinkedIn bounces with `ERR_TOO_MANY_REDIRECTS`). A persistent redirect loop ⇒ the `li_at` is expired/challenged → re-seed a fresh one.
5. **The daemon keeps ONE browser alive** and does all actions in it — far more robust than repeated `testconnect` relaunches. Run the daemon, don't burst test commands.
6. **Environment matters:** VMs / datacenter IPs get flagged fast. A residential IP and a warmed account are the real reliability levers.

`connection_status` is derived in `controlcenter/services.py:derive_connection_status` from the saved `li_at` expiry (no browser launch), and stamped `connected`/`checkpoint` by the daemon.

---

## 🎯 Prospecting pipeline & testing a connection

Flow for a **regular** campaign (`linkedin/pipeline/`):

```
handle_connect → find_candidate → ready_source:
   find_ready_candidate (READY_TO_CONNECT leads, GP-ranked; FIFO fallback on cold start)
   └ promote_to_ready (QUALIFIED→READY; GP-gated when fitted, LLM-gated batch on cold start)
       └ qualify_source → run_qualification (LLM labels) ← search_source → run_search (LLM keywords + LinkedIn search)
```

**Cold-start fix (why connecting now works):** a brand-new campaign has no GP labels, so the model can't gate. Previously `promote_to_ready` and `find_ready_candidate` both returned nothing until ≥2 labels of each class existed → it never sent a first connection. Now:
- `promote_to_ready` promotes a bounded batch (`COLD_START_PROMOTE_BATCH=5`) of LLM-qualified leads on cold start.
- `find_ready_candidate` falls back to FIFO when the GP can't rank.
- The GP gate resumes automatically once it has enough data.

**Fastest way to test a connection (deterministic):** seed a profile directly as `READY_TO_CONNECT`, then run the daemon — it connects on the first connect slot without waiting for the search/qualify ramp:

```python
# venv/bin/python manage.py shell
from linkedin.models import Campaign
from crm.models import Lead, Deal
from linkedin_cli.enums import ProfileState
c = Campaign.objects.get(name="Cashera ISO Partnerships")
lead,_ = Lead.objects.get_or_create(public_identifier="sirojboboev",
        defaults={"linkedin_url":"https://www.linkedin.com/in/sirojboboev/"})
d,_ = Deal.objects.get_or_create(lead=lead, campaign=c)
d.state = ProfileState.READY_TO_CONNECT.value; d.outcome=""; d.save()
```

(`sirojboboev` is already seeded this way.) Or use `manage.py testconnect --profile <url>` to fire the connect action directly (single browser launch).

---

## 🩺 Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Nothing happens" after Start | Daemon not running, or campaign `enabled=False`, or login not established. Check `make run` logs + `connection_status`. |
| `ERR_TOO_MANY_REDIRECTS` at `/feed/` | `li_at` expired/challenged, or rapid relaunches tripped anti-automation. Re-seed a fresh `li_at`; run the daemon (not burst tests); use a residential IP. |
| `auth_context_expired` / `/flagship-web/login/` | Scripted login blocked — use `setcookie` cookie path. |
| Daemon logs `RESOLVE CHECKPOINT` | Clear the challenge in the daemon's headed browser window (or noVNC in Docker) until it reaches the feed. |
| No connections ever sent, no errors | Was the cold-start stall (now fixed). Ensure on latest `main`. For a quick check, seed a READY lead (above). |
| Campaign uses wrong pipeline | A real prospecting campaign must be `is_freemium=False`. Freemium uses a seed/kit pipeline. |
| SPA shows "not built" page | Run `make frontend-build`. |
| `make web`/`make run` → "python: not found" | Use the venv; the Makefile auto-detects `venv/bin/python`. |

---

## ✅ Testing & deployment

- `make test` (or `venv/bin/python -m pytest`) — full suite (~300 tests). API tests in `tests/api/test_controlcenter.py`; run-control/queue in `tests/test_run_control.py`; cold-start in `tests/test_ready_pool.py`.
- Migrations check: `venv/bin/python manage.py makemigrations --check`.
- Docker builds the SPA in a node stage and runs `app` (daemon) + `web` services (`local.yml`, `compose/linkedin/{start,start-web}`).

## 📦 Git / publishing

- Remote: `github.com/Cristianbene00/OpenOutreach` (HTTPS). Pushing needs a token or SSH.
- Convention (per `CLAUDE.md`): single-line commit messages, **no `Co-Authored-By`**, deps in `requirements/*.txt`, keep `CLAUDE.md`/`ARCHITECTURE.md` in sync.
- To stop pasting tokens: add an SSH key (`ssh-keygen -t ed25519 ...`, add to GitHub) and switch `origin` to the SSH URL.
