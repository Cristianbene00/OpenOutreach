# linkedin/pipeline/ready_pool.py
"""Ready-to-connect pool: GP confidence gate between NEW and READY_TO_CONNECT."""
from __future__ import annotations

import logging

import numpy as np

from linkedin.db.deals import (
    get_qualified_profiles,
    get_ready_to_connect_profiles,
    set_profile_state,
)
from linkedin.ml.qualifier import BayesianQualifier
from linkedin_cli.enums import ProfileState

logger = logging.getLogger(__name__)

# On cold start the GP can't gate yet, so promotion is LLM-gated. Promote at
# most this many QUALIFIED leads per call so connecting starts without dumping
# a huge backlog into READY at once (actual sends are still daily-rate-limited).
COLD_START_PROMOTE_BATCH = 5


def promote_to_ready(session, qualifier: BayesianQualifier, threshold: float) -> int:
    """Promote QUALIFIED profiles to READY_TO_CONNECT. Returns the count promoted.

    Two regimes:
    - **GP fitted** — promote profiles whose GP confidence ``P(f>0.5)`` clears
      ``threshold`` (the quality gate, once there's data to gate on).
    - **Cold start** (GP not fitted) — the LLM already qualified these leads, so
      promote a bounded batch directly. The GP gate takes over once it fits.
      Without this a fresh campaign never connects (the GP needs labels, but
      nothing reaches READY to generate connect activity).

    Returns 0 only when there are no QUALIFIED profiles with embeddings.
    """
    from crm.models import Lead

    profiles = get_qualified_profiles(session)
    if not profiles:
        return 0

    embeddings = []
    valid = []
    for p in profiles:
        lead = Lead.objects.filter(pk=p.get("lead_id")).first()
        emb = lead.get_embedding(session) if lead else None
        if emb is not None:
            embeddings.append(emb)
            valid.append(p)

    if not valid:
        return 0

    X = np.array(embeddings, dtype=np.float64)
    probs = qualifier.predict_probs(X)

    if probs is None:
        # Cold start — LLM-gated promotion of a bounded batch.
        batch = valid[:COLD_START_PROMOTE_BATCH]
        for p in batch:
            set_profile_state(session, p["public_identifier"], ProfileState.READY_TO_CONNECT.value)
        logger.info(
            "Cold start — promoted %d LLM-qualified profile(s) to READY_TO_CONNECT "
            "(GP not fitted yet)", len(batch),
        )
        return len(batch)

    promoted = 0
    for prob, p in zip(probs, valid):
        if prob > threshold:
            pid = p.get("public_identifier", "?")
            logger.info("%s READY_TO_CONNECT (P(f>0.5)=%.3f)", pid, prob)
            set_profile_state(session, p["public_identifier"], ProfileState.READY_TO_CONNECT.value)
            promoted += 1

    return promoted


def find_ready_candidate(session, qualifier: BayesianQualifier) -> dict | None:
    """Return the next READY_TO_CONNECT profile to connect, or None if none exist.

    Prefers the GP's top-ranked profile when the model is fitted. On cold start
    (ranking unavailable) it falls back to FIFO: a deal that is *already*
    READY_TO_CONNECT should always be connectable — the GP confidence gate
    applies at promotion (``promote_to_ready``), not here.
    """
    profiles = get_ready_to_connect_profiles(session)
    if not profiles:
        return None

    ranked = qualifier.rank_profiles(profiles, session=session)
    if ranked:
        return ranked[0]

    logger.debug(
        "find_ready_candidate: ranking unavailable (cold start) — "
        "FIFO over %d READY_TO_CONNECT profile(s)", len(profiles),
    )
    return profiles[0]
