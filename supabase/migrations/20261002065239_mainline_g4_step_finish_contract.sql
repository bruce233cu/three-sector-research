begin;
alter table public.automation_run_steps alter column finished_at drop not null;
alter table public.automation_run_steps add constraint automation_run_steps_finish_contract check (finished_at is not null or step_code='mainline_job');
commit;
