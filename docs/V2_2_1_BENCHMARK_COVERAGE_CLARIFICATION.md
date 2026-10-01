# V2.2.1 Clarification — ALL_A_EQUAL_WEIGHT benchmark coverage

User-authorized clarification, 2026-10-01. This is an explicit supplement to
the original V2.2 frozen specification; it does not rewrite that document.

ALL_A_EQUAL_WEIGHT uses the real, effective historical A-share universe for
each target trading day and the arithmetic mean of valid individual daily
returns. Include ST shares, exclude non-A securities and future listings;
retain securities through their delisting date. Missing or suspended returns
are unavailable observations, never synthetic zeros.

Daily benchmark coverage = valid individual daily return count / historical
A-share universe count. A verified denominator is required; an unknown
denominator means NULL coverage, not 0%. At coverage >=95%, output the mean.
Below 95%, benchmark_return=NULL and existing Freeze applies. Dependent RS
uses only valid daily benchmark observations, never substituted zeros.

The 95% threshold applies only to benchmark daily cross-sectional availability.
RS historical-window validity remains 90%. Original sector/breadth internal
coverage remains 70%. No threshold is lowered for the fixed 15 samples.

801003 is the existing SWS provider index identifier. Its inputs have not
proved equivalence to this arithmetic historical-universe benchmark. It is
excluded from V2.2.1 benchmark and all-A turnover denominator inputs. A mismatch
affects benchmark_return, RS5/10/20 and downstream RS-derived fields; the old
801003 amount proxy also invalidates turnover_share/turnover_intensity.

Provider, request window/time, historical universe certification, return
semantics, checksum, row count, coverage, code SHA, parameter hash and run ID
must be retained. Permanent original HTTP bodies are not by themselves a G1
requirement when sufficient auditable evidence exists. Never fabricate source
IDs or certify partial/current-only universes as historical all-A universes.
