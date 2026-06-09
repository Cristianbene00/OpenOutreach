# tests/test_ready_pool.py
import pytest
from unittest.mock import patch

import numpy as np

from linkedin.db.deals import set_profile_state
from linkedin.db.leads import create_enriched_lead, promote_lead_to_deal
from linkedin.ml.qualifier import BayesianQualifier
from linkedin_cli.enums import ProfileState
from linkedin.pipeline.ready_pool import promote_to_ready, find_ready_candidate


SAMPLE_PROFILE = {
    "first_name": "Alice",
    "last_name": "Smith",
    "headline": "Engineer",
    "positions": [{"company_name": "Acme"}],
}


def _make_qualified(session, public_id="alice"):
    url = f"https://www.linkedin.com/in/{public_id}/"
    create_enriched_lead(session, url, SAMPLE_PROFILE)
    promote_lead_to_deal(session, public_id)


@pytest.mark.django_db
class TestPromoteToReady:
    @pytest.fixture(autouse=True)
    def _db(self, db):
        pass

    def test_promotes_above_threshold(self, fake_session):
        _make_qualified(fake_session, "alice")
        _make_qualified(fake_session, "bob")

        scorer = BayesianQualifier(seed=42)

        with patch(
            "crm.models.lead.Lead.get_embedding",
            return_value=np.ones(384),
        ), patch.object(
            scorer, "predict_probs", return_value=np.array([0.95, 0.80]),
        ):
            count = promote_to_ready(fake_session, scorer, threshold=0.9)

        assert count == 1

        from crm.models import Deal
        alice_deal = Deal.objects.get(lead__linkedin_url="https://www.linkedin.com/in/alice/")
        bob_deal = Deal.objects.get(lead__linkedin_url="https://www.linkedin.com/in/bob/")
        assert alice_deal.state == ProfileState.READY_TO_CONNECT
        assert bob_deal.state == ProfileState.QUALIFIED

    def test_promotes_llm_qualified_on_cold_start(self, fake_session):
        # Cold start (GP unfitted): the LLM already qualified the lead, so it
        # should be promoted directly so connecting can begin.
        _make_qualified(fake_session)

        scorer = BayesianQualifier(seed=42)

        with patch(
            "crm.models.lead.Lead.get_embedding",
            return_value=np.ones(384),
        ), patch.object(
            scorer, "predict_probs", return_value=None,
        ):
            assert promote_to_ready(fake_session, scorer, threshold=0.9) == 1

        from crm.models import Deal
        deal = Deal.objects.get(lead__linkedin_url="https://www.linkedin.com/in/alice/")
        assert deal.state == ProfileState.READY_TO_CONNECT

    def test_cold_start_promotion_is_bounded(self, fake_session):
        from linkedin.pipeline.ready_pool import COLD_START_PROMOTE_BATCH

        for i in range(COLD_START_PROMOTE_BATCH + 2):
            _make_qualified(fake_session, f"lead{i}")

        scorer = BayesianQualifier(seed=42)
        with patch(
            "crm.models.lead.Lead.get_embedding", return_value=np.ones(384),
        ), patch.object(scorer, "predict_probs", return_value=None):
            promoted = promote_to_ready(fake_session, scorer, threshold=0.9)

        assert promoted == COLD_START_PROMOTE_BATCH

    def test_returns_zero_on_empty_pool(self, fake_session):
        scorer = BayesianQualifier(seed=42)
        assert promote_to_ready(fake_session, scorer, threshold=0.9) == 0


@pytest.mark.django_db
class TestGetReadyCandidate:
    @pytest.fixture(autouse=True)
    def _db(self, db):
        pass

    def test_returns_none_when_empty(self, fake_session):
        scorer = BayesianQualifier(seed=42)
        assert find_ready_candidate(fake_session, scorer) is None

    def test_returns_top_ranked(self, fake_session):
        _make_qualified(fake_session, "alice")
        set_profile_state(fake_session, "alice", ProfileState.READY_TO_CONNECT.value)

        scorer = BayesianQualifier(seed=42)
        scorer.rank_profiles = lambda profiles, **kw: profiles

        result = find_ready_candidate(fake_session, scorer)
        assert result is not None
        assert result["public_identifier"] == "alice"

    def test_cold_start_falls_back_to_fifo(self, fake_session):
        # GP can't rank (cold start) — an already-READY lead must still be
        # selectable rather than stranded.
        _make_qualified(fake_session, "alice")
        set_profile_state(fake_session, "alice", ProfileState.READY_TO_CONNECT.value)

        scorer = BayesianQualifier(seed=42)
        scorer.rank_profiles = lambda profiles, **kw: []  # cold start

        result = find_ready_candidate(fake_session, scorer)
        assert result is not None
        assert result["public_identifier"] == "alice"
