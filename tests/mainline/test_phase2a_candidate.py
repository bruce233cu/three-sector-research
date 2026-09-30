from src.mainline.metrics.candidate import MetricValue, strongest_percentiles, turnover_metrics, win_rate
from src.mainline.rules.candidate import evaluate_s1


def m(value=None, valid=True, reason=None):
    return MetricValue(value, valid, 1.0 if valid else 0.0, reason)


def metrics(c1=m(.1), c2=m(.01), c3=m(.8), c4=m(.01), c4b=m(1.2), c5=m(.1), c5b=m(.1)):
    return {"rs_5_cross_section_percentile": c1, "rs_10": c2, "win_5": c3,
            "turnover_share_vs_20d": c4, "turnover_intensity": c4b,
            "up_ratio_vs_all_a": c5, "above_ma20_vs_all_a": c5b}


def test_fewer_than_four_valid_is_data_insufficient():
    result = evaluate_s1(metrics(c4=m(None, False), c4b=m(None, False), c5=m(None, False), c5b=m(None, False)))
    assert result["valid_condition_count"] == 3
    assert result["final_decision"] == "DATA_INSUFFICIENT"


def test_three_of_five_pass_is_s1():
    result = evaluate_s1(metrics(c4=m(-.1), c4b=m(.8), c5=m(-.1), c5b=m(-.1)))
    assert result["pass_condition_count"] == 3
    assert result["final_decision"] == "S1"


def test_two_of_five_pass_is_s0():
    result = evaluate_s1(metrics(c3=m(.4), c4=m(-.1), c4b=m(.8), c5=m(-.1), c5b=m(-.1)))
    assert result["pass_condition_count"] == 2
    assert result["final_decision"] == "S0"


def test_null_condition_is_not_false():
    result = evaluate_s1(metrics(c5=m(None, False, "missing"), c5b=m(None, False, "missing")))
    assert result["conditions"]["C5"]["valid"] is False
    assert result["conditions"]["C5"]["passed"] is None


def test_cross_section_fewer_than_ten_is_invalid():
    result = strongest_percentiles({str(i): m(i / 10) for i in range(9)})
    assert all(not item.valid and item.value is None for item in result.values())


def test_turnover_history_below_twenty_is_invalid():
    result = turnover_metrics(range(1, 20), range(10, 29))
    assert result["turnover_share_20d_mean"].valid is False


def test_win_uses_valid_comparison_denominator():
    result = win_rate([1, None, 2, 3, 4], [0, 0, 1, 4, 3], window=5)
    assert result.valid and result.value == .75 and result.coverage == .8


def test_rerun_is_identical():
    first = evaluate_s1(metrics())
    second = evaluate_s1(metrics())
    assert first == second


def test_rule_version_is_result_identity_not_overwrite():
    old = evaluate_s1(metrics(), rule_version="V2.2-S1")
    new = evaluate_s1(metrics(), rule_version="future-test-only")
    assert old["final_decision"] == new["final_decision"]
    assert old["rule_version"] != new["rule_version"]
