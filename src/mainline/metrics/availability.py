"""Opt-in V2.2.1 policy; the frozen V2.2 calculator is unchanged."""
from dataclasses import replace
from typing import Any

from .sector import SectorMetricInput, calculate_sector_snapshot

RULE_VERSION = "mainline_v2.2.1"
PROFILE_ID = "industry_trend_v2_2_1_fast_close"
AVAILABILITY_VERSION = "mainline_metric_availability_v2.2.1_deferred_circ_mv"
DEFERRED_METRICS = ("turnover_cap_deviation", "top3_return_contribution")


def calculate_v221_snapshot(value: SectorMetricInput) -> dict[str, Any]:
    """Compute original core formulas; never consume unproven circ_mv.

    This calculation does not certify provider semantics or G1. The caller
    must independently validate benchmark identity, the all-A amount universe,
    source-level quality and PIT before accepting/persisting the result.
    """
    core_input = replace(
        value,
        member_bars=value.member_bars.drop(columns=["circ_mv"], errors="ignore"),
        all_a_circ_mv=None,
    )
    result = calculate_sector_snapshot(core_input)
    result.update(
        rule_version=RULE_VERSION,
        profile_id=PROFILE_ID,
        parameter_profile=PROFILE_ID,
        metric_availability_version=AVAILABILITY_VERSION,
        circ_mv_status="deferred",
    )
    availability = {
        key: {
            "status": "deferred_due_to_unproven_historical_circ_mv",
            "role": "optional_enhancement",
            "state_rule_policy": "inactive_when_unavailable",
        }
        for key in DEFERRED_METRICS
    }
    for key in DEFERRED_METRICS:
        result[key] = None
        result["metric_coverage_json"][key] = 0.0
    result["decision_reason"] = {
        "metric_availability_version": AVAILABILITY_VERSION,
        "circ_mv_status": "deferred",
        "metric_availability": availability,
        "provider_semantics_validation_required": True,
    }
    return result
