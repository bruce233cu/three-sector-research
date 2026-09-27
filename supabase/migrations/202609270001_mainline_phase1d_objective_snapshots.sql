begin;

-- Phase 1D stores objective sector measurements only.  A status is intentionally
-- absent until Phase 2 applies the frozen state rules.
alter table mainline.daily_mainline_snapshot alter column hard_status drop not null;

alter table mainline.daily_mainline_snapshot
  add column if not exists taxonomy_code text,
  add column if not exists taxonomy_version text,
  add column if not exists member_count integer check (member_count is null or member_count >= 0),
  add column if not exists sector_return numeric,
  add column if not exists benchmark_return numeric,
  add column if not exists source_snapshot_ids uuid[],
  add column if not exists pit_level text check (pit_level is null or pit_level in ('effective_pit','strict_knowledge_pit')),
  add column if not exists knowledge_time_unverified boolean not null default false,
  add column if not exists cache_checksum text;

comment on column mainline.daily_mainline_snapshot.hard_status is
  'NULL during Phase 1D objective-metric POC; S0-S4 is assigned only by the later frozen state machine.';
comment on column mainline.daily_mainline_snapshot.pit_level is
  'effective_pit validates membership intervals; strict_knowledge_pit additionally validates knowledge-time availability.';

commit;
