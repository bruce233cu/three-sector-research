begin;
alter table public.automation_run_steps drop constraint automation_run_steps_status_check;
alter table public.automation_run_steps add constraint automation_run_steps_status_check check (status in ('succeeded','skipped','failed') or (step_code='mainline_job' and status in ('running','partial')));
commit;
