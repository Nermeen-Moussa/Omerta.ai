"""Layer 3 engine + step-up tests (no DB, no model artifacts required)."""

from domain.services import layer3_engine as l3
from domain.services import step_up_service as su


class StubScorer:
    def __init__(self, score):
        self._s = score

    def score(self, features):
        return {"final_score": self._s, "rule_score": 0, "ml_score": self._s,
                "fraud_probability": self._s / 100, "anomaly_score": self._s,
                "isolation_forest_flag": False, "reasons": []}


def test_tier_boundaries_match_design_notes():
    assert l3.tier_for(0) == "LOW" and l3.tier_for(30) == "LOW"
    assert l3.tier_for(31) == "MEDIUM" and l3.tier_for(70) == "MEDIUM"
    assert l3.tier_for(71) == "HIGH" and l3.tier_for(100) == "HIGH"


def test_actions_per_tier():
    assert l3.assess(l3.TransferRiskContext(amount=50), StubScorer(10)).action == l3.ALLOW
    assert l3.assess(l3.TransferRiskContext(amount=50), StubScorer(50)).action == l3.STEP_UP
    assert l3.assess(l3.TransferRiskContext(amount=50), StubScorer(90)).action == l3.BLOCK_ESCALATE


def test_third_party_takeover_typology():
    ctx = l3.TransferRiskContext(amount=9000, is_new_device=True, is_vpn=True, hist_avg=100, hist_max=300)
    d = l3.assess(ctx, StubScorer(80))
    assert d.typology == l3.THIRD_PARTY and d.action == l3.BLOCK_ESCALATE


def test_scam_typology_known_session_new_beneficiary_big_amount():
    ctx = l3.TransferRiskContext(amount=5000, hist_count=20, hist_avg=200, hist_max=500,
                                 hist_std=80, is_new_beneficiary=True)
    d = l3.assess(ctx, StubScorer(55))
    assert d.typology == l3.SCAM and d.action == l3.STEP_UP


def test_first_party_typology_prior_alerts_familiar_session():
    ctx = l3.TransferRiskContext(amount=100, hist_count=30, hist_avg=100, hist_max=200, previous_alert_count=3)
    assert l3.assess(ctx, StubScorer(35)).typology == l3.FIRST_PARTY


def test_impossible_travel_forces_high_even_if_model_says_low():
    d = l3.assess(l3.TransferRiskContext(amount=10, impossible_travel=True), StubScorer(5))
    assert d.tier == "HIGH" and d.action == l3.BLOCK_ESCALATE


def test_feature_mapping_is_complete_and_ratio_correct():
    from infrastructure.risk.fraudguard import FEATURE_COLUMNS
    f = l3.build_features(l3.TransferRiskContext(amount=1000, hist_avg=100, hist_max=250, hist_std=50))
    assert set(FEATURE_COLUMNS) <= set(f)
    assert f["amount_to_avg_ratio"] == 10 and f["amount_to_max_ratio"] == 4 and f["amount_zscore"] == 18


def test_falls_back_to_rules_only_when_models_unavailable():
    class Broken:
        def score(self, features):
            raise RuntimeError("xgboost not installed")

    ctx = l3.TransferRiskContext(amount=9500, hist_avg=100, hist_max=300, hist_std=40,
                                 is_new_device=True, is_vpn=True, is_new_country=True)
    d = l3.assess(ctx, Broken())
    assert d.source == "RULES_ONLY" and d.score > 0 and d.reasons


def test_step_up_roundtrip_binding_single_use_and_attempt_limit():
    kw = dict(customer_id=1, recipient="OM-2", amount="500.00", currency="EGP")
    ch = su.issue_challenge(**kw, include_dev_code=True)
    assert not su.verify_challenge(challenge_id=ch["challenge_id"], code="000000", **kw) or ch["dev_code"] == "000000"
    ch = su.issue_challenge(**kw, include_dev_code=True)
    # bound to the transfer: different amount must fail
    assert not su.verify_challenge(challenge_id=ch["challenge_id"], code=ch["dev_code"],
                                   **{**kw, "amount": "9999.00"})
    assert su.verify_challenge(challenge_id=ch["challenge_id"], code=ch["dev_code"], **kw)
    # single use
    assert not su.verify_challenge(challenge_id=ch["challenge_id"], code=ch["dev_code"], **kw)


def test_step_up_locks_after_three_wrong_codes():
    kw = dict(customer_id=1, recipient="OM-2", amount="1.00", currency="EGP")
    ch = su.issue_challenge(**kw, include_dev_code=True)
    wrong = "111111" if ch["dev_code"] != "111111" else "222222"
    for _ in range(3):
        assert not su.verify_challenge(challenge_id=ch["challenge_id"], code=wrong, **kw)
    assert not su.verify_challenge(challenge_id=ch["challenge_id"], code=ch["dev_code"], **kw)


def test_recipient_age_is_neutral_for_model_unless_enabled_but_still_used_for_typology():
    young = l3.TransferRiskContext(amount=100, recipient_account_age_days=1, is_new_beneficiary=True,
                                   hist_avg=100, hist_max=200, hist_std=10, hist_count=10)
    assert l3.build_features(young)["merchant_age_days"] == 999
    young.use_recipient_age_feature = True
    assert l3.build_features(young)["merchant_age_days"] == 1
    young.use_recipient_age_feature = False
    typ, reasons = l3.classify_typology(young, l3.build_features(young))
    assert typ == l3.SCAM and any("under 7 days" in r for r in reasons)
