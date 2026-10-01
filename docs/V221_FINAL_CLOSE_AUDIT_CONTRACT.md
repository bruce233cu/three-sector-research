# V2.2.1 FINAL CLOSE audit contract

This continues actual branch HEAD 25d27a0ff903eee49402832ece6fdad3e121fc89;
the user-supplied 52da934 SHA is an earlier checkpoint, not a rollback target.

Authoritative business definitions: V2.2 frozen specification sections 5–7,
plus the explicit user-approved V2.2.1 circ_mv deferred and benchmark daily
95% availability clarifications. No standalone metric_contract.md exists at
the resume HEAD; this does not authorize inventing a replacement definition.

The previous 15 V2.2.1 DATA_UNAVAILABLE snapshots are audit facts, not a
completed real-Sina POC. Preserve them. New real-input results use the separate
industry_trend_v2_2_1_final_close audit profile with unchanged business thresholds
and mainline_v2.2.1. No core schema modification is needed.

The final collector uses only the existing SinaWindow implementation and the
existing AKShare official-exchange security-master route. The all-A universe
must include historical delisted shares and exclude future listings/non-A
assets. A current active list, a partial exchange ledger, or a guessed security
code migration is not a certified historical all-A denominator. If certification
is absent, benchmark coverage and return remain NULL. Fetching more prices
cannot certify an unknown universe.

801003 remains an external SWS index, never a V2.2.1 benchmark/turnover input.
Current official index identity is verifiable; historical published SWS index
methodology uses circulating-share weighting and chain-link calculation. Its
exact current 801003 revision/universe is not fully evidenced in this project,
so no full current methodology is asserted or silently equated with arithmetic
equal weighting. Matching daily values by coincidence does not prove equivalence.

Source evidence must describe actual successful data, provider/upstream,
request scope/time, normalized checksum, upstream response checksum when
available, rows, coverage, run/code/parameter identifiers and evidence grade.
Failed requests remain acquisition logs, not placeholder source snapshots.
Normalized data can reside in temporary workflow artifacts; permanent complete
HTTP payload retention alone is not a G1 condition.

Final acceptance is distinct from workflow success. SUCCESS means complete
required evidence and no core Freeze; PARTIAL means real usable sector input
but missing required evidence or insufficient coverage; FAIL means no usable
sector input or invalid membership. Exact-calendar MA20/60 and NEW_HIGH60,
90% RS validity, NULL propagation, membership rejection, circ_mv deferred
without Freeze, and same-input deterministic outputs must be checked.

Execution remains entirely within mainline. Do not write the shared three-sector
public optimization log; append the plain-language change record to the mainline
manifest and this delivery package instead, respecting the user's explicit
module-isolation instruction over AGENTS.md's shared-log default.
