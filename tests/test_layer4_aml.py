"""Layer 4 AML pattern tests (pure logic, no DB / Neo4j)."""

from datetime import UTC, datetime, timedelta

from domain.services import layer4_aml as l4

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def E(i, src, dst, amt, hours_ago, cur="EGP"):
    return l4.Edge(f"T{i}", src, dst, amt, cur, NOW - timedelta(hours=hours_ago))


def patterns(edges, focus):
    return {f.pattern for f in l4.analyze(edges, [focus], NOW)}


def test_structuring_detected_for_sub_threshold_series():
    edges = [E(i, 1, 2, a, h) for i, (a, h) in enumerate([(45000, 30), (48000, 20), (47000, 5)])]
    f = [x for x in l4.analyze(edges, [1], NOW) if x.pattern == "STRUCTURING"]
    assert f and f[0].evidence["count"] == 3 and f[0].severity in ("HIGH", "CRITICAL", "MEDIUM")


def test_normal_activity_not_flagged():
    edges = [E(1, 1, 2, 200, 10), E(2, 1, 3, 150, 30), E(3, 1, 2, 5000, 50)]
    assert patterns(edges, 1) == set()


def test_single_large_transfer_is_not_structuring():
    assert "STRUCTURING" not in patterns([E(1, 1, 2, 90000, 1)], 1)


def test_old_transfers_outside_window_ignored():
    edges = [E(i, 1, 2, 45000, 100 + i) for i in range(4)]
    assert "STRUCTURING" not in patterns(edges, 1)


def test_amounts_below_half_threshold_not_structuring():
    edges = [E(i, 1, 2, 20000, i + 1) for i in range(6)]
    assert "STRUCTURING" not in patterns(edges, 1)


def test_fan_out_to_many_recipients():
    edges = [E(i, 1, 10 + i, 12000, i + 1) for i in range(6)]
    assert "FAN_OUT" in patterns(edges, 1)


def test_fan_in_collector_account():
    edges = [E(i, 20 + i, 1, 11000, i + 1) for i in range(6)]
    assert "FAN_IN" in patterns(edges, 1)


def test_pass_through_layering():
    edges = [E(1, 5, 1, 30000, 3), E(2, 1, 6, 28000, 2)]
    assert "PASS_THROUGH" in patterns(edges, 1)


def test_cycle_a_b_c_a():
    edges = [E(1, 1, 2, 1000, 5), E(2, 2, 3, 990, 4), E(3, 3, 1, 980, 3)]
    assert "CYCLE" in patterns(edges, 1)


def test_currency_specific_threshold_usd():
    edges = [E(i, 1, 2, 800, i + 1, cur="USD") for i in range(3)]
    assert "STRUCTURING" in patterns(edges, 1)


def test_results_sorted_strongest_first():
    edges = [E(i, 1, 10 + i, 46000, i + 1) for i in range(6)]
    scores = [f.score for f in l4.analyze(edges, [1], NOW)]
    assert scores == sorted(scores, reverse=True) and scores
