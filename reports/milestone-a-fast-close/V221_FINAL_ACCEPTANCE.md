# G1 DATA GATE — V2.2.1 FINAL

G1 = FAIL
READY_FOR_PRODUCTION_ENABLEMENT = false
MILESTONE A remains open. No Phase 2 work was started.

## Explicit clarification implemented

User-authorized 2026-10-01 clarification is recorded separately in
`docs/V2_2_1_BENCHMARK_COVERAGE_CLARIFICATION.md`; original V2.2 specification
and original profile were not rewritten. Daily ALL_A_EQUAL_WEIGHT coverage
must reach 95%; RS window coverage remains 90%; sector internal coverage remains
70%. Unknown historical universe denominator yields NULL coverage, NULL return
and Freeze. No 801003 substitution, future listings, synthetic zero returns or
threshold reductions are accepted.

The new isolated benchmark calculator applies historical listing/delisting,
A-share filtering, equal weighting and explicit availability. Its V2.2.1 wrapper
uses exact market-calendar RS/turnover windows, propagates missing daily
benchmark returns and preserves circ_mv deferred policy. Six meaningful tests
passed locally and in GitHub Actions, including 94/95% boundary, future/B-share/
delisted exclusion, duplicate rejection, nonfinite inputs, missing-data Freeze,
90% RS window validity and deterministic recomputation.

## Verified continuation state

Resume HEAD: 52da9346398e4513d4fe0b85ec19030b2c76421e.
Implementation: 7e250fefd10c5f810e60a6ad76c95abdb70de1d9.
Successful final execution: 20c0edc910fc45f5e472d421da8df3563ec11e44.
Workflow run: 36885241757; artifact: 11174431186.
Artifact SHA256: 88d41cc840bc7796d7f31785271f371484a7cd42d9b6c08b33790714963138cf.

Existing SSE calendar, source recovery and deferred policy were retained. No
calendar rebuild, circ_mv/Tushare research, large provider tests, Sites, Daily
Pipeline or three-sector changes were performed. One bounded historical
universe acquisition through the existing Baostock route timed out after 50
seconds. It was not retried; its real failure evidence is preserved. The
security_master and stock_daily tables each contained zero rows. No full-A
window cache was available. The runner does not claim empty inputs are a
complete historical universe.

## Source lineage audit

Legacy fixed samples: 15; complete membership + nonempty stock + legacy
benchmark chains: 5; restoration affected samples:
6; incomplete chains: 10.
Restoration (already completed): 4 real registry entries, 9 references across
6 samples. These counts overlap the chain status counts; they are not partitions.
Six samples reference empty stock sources; four have only the legacy benchmark
reference. Dangling source references are zero. Registry recovery alone does
not prove valid data or equivalence of 801003 to equal weighting.

New snapshots have 14 real normalized membership evidence sources and the
existing calendar source. There are no fabricated stock or benchmark sources.
One sample (2020-06-30 / 801120) has no readable member records in the usable
artifacts. The final-v2 membership file is invalid UTF-8 at byte 393218. Existing
runtime, three-sample and fallback artifacts were read without modifying them;
14 samples pass only their membership effective-date checks. Complete new
membership + stock + ALL_A benchmark chains: 0/15. Knowledge-time and complete
stock/universe PIT are not certified. The immutable membership source was
registered for audit only, disabled for production.

## Formal snapshot and acceptance result

15 formal `mainline_v2.2.1 / industry_trend_v2_2_1_fast_close` rows were appended
to daily_mainline_snapshot; all 15 are explicit frozen DATA_UNAVAILABLE results.
Old 15 snapshots/sample runs were retained. Benchmark, RS5/10/20 and deferred
circ_mv metrics are NULL for all 15. Benchmark coverage is NULL because the
true denominator is unknown; it is not falsely reported as 0%.

Run ID: 62c078a6-7033-444b-a868-7f593dc54c3d.
Recompute ID: 1de58258-5808-486f-b694-d9271c27aabc.
Parameter hash: 2275d533acc156f7817d09f22f738e130a048e0b2cfc0a2110d64ac675eedc73.
Both run manifests and all genuine source references were written and verified.
The two calculations match for all 15 frozen results. This proves deterministic
missing-input handling, not repeatability of complete real-data calculations.
Real-data repeatability acceptance is therefore false.

The final SQL gate read persisted rows and returned {"G1":"FAIL","READY_FOR_PRODUCTION_ENABLEMENT":false,"formal_count":15,"frozen_count":15,"critical_ok_count":0,"benchmark_available_count":0,"null_propagation_count":15,"deferred_null_count":15,"lineage_claim_count":0,"membership_effective_date_count":14,"complete_chain_count":0,"dangling_count":"0"}.
Coverage/Freeze implementation tests pass. Complete real-data coverage, PIT,
lineage and repeatability acceptance fail. Permanent HTTP payload retention
was not used as an automatic blocker.

## Blocking issues (2)

1. Certified historical ALL_A universes and valid daily return/amount windows
   are absent; no sample has a valid >=95% equal-weight benchmark.
2. The 15 samples lack complete auditable stock/ALL_A input chains and complete
   real-data PIT/recomputation evidence; one membership payload is also missing.

## Mainline-only optimization record

2026-10-01 / V2.2.1: 明确记录95%等权benchmark可用性补充规则，保留90% RS与
70%板块阈值，新增独立计算和六项验证。写入15条正式冻结结果与两份运行manifest，
无旧快照覆盖。真实输入不全使最终G1失败，禁止把空输入复算一致当作生产就绪。
遵从用户禁止非mainline影响的指令，优化记录保存在mainline manifest及此报告，
未写入三大赛道共享public优化记录表。
