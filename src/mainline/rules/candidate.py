from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.mainline.metrics.candidate import MetricValue


@dataclass(frozen=True)
class Condition:
    valid: bool
    passed: bool | None
    value: Any
    reason: str | None = None

    def dict(self) -> dict:
        return asdict(self)


def _single(metric: MetricValue, predicate) -> Condition:
    if not metric.valid or metric.value is None:
        return Condition(False, None, metric.value, metric.reason_if_invalid)
    return Condition(True, bool(predicate(metric.value)), metric.value)


def _either(a: MetricValue, a_pred, b: MetricValue, b_pred) -> Condition:
    usable = [("a", a, a_pred), ("b", b, b_pred)]
    outcomes = [(name, metric.value, bool(pred(metric.value))) for name, metric, pred in usable if metric.valid and metric.value is not None]
    if not outcomes:
        return Condition(False, None, {"a": a.value, "b": b.value}, "both_inputs_invalid")
    return Condition(True, any(item[2] for item in outcomes), {"a": a.value, "b": b.value})


def evaluate_s1(metrics: dict[str, MetricValue], *, rule_version: str = "V2.2-S1", parameter_profile: str = "V2.2-frozen") -> dict:
    conditions = {
        "C1": _single(metrics["rs_5_cross_section_percentile"], lambda v: v <= .20),
        "C2": _single(metrics["rs_10"], lambda v: v > 0),
        "C3": _single(metrics["win_5"], lambda v: v >= .60),
        "C4": _either(metrics["turnover_share_vs_20d"], lambda v: v > 0, metrics["turnover_intensity"], lambda v: v > 1),
        "C5": _either(metrics["up_ratio_vs_all_a"], lambda v: v > 0, metrics["above_ma20_vs_all_a"], lambda v: v > 0),
    }
    valid = sum(condition.valid for condition in conditions.values())
    passed = sum(condition.passed is True for condition in conditions.values())
    decision = "DATA_INSUFFICIENT" if valid < 4 else "S1" if passed >= 3 else "S0"
    reason = f"valid={valid}, pass={passed}; " + ("有效条件不足4个" if valid < 4 else "至少3个条件通过" if passed >= 3 else "通过条件不足3个")
    return {
        "conditions": {key: value.dict() for key, value in conditions.items()},
        "valid_condition_count": valid,
        "pass_condition_count": passed,
        "final_decision": decision,
        "decision_reason": reason,
        "rule_version": rule_version,
        "parameter_profile": parameter_profile,
    }
