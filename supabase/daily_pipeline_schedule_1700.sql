-- Runtime configuration only; preserve existing job id, credentials and unrelated jobs.
do $block$
declare j record;
begin
 select jobid,command into strict j from cron.job where jobname='v43-daily-research-pipeline';
 perform cron.alter_job(j.jobid,schedule:='0 9 * * *',
 command:=replace(j.command,'current_date',$$ (now() at time zone 'Asia/Shanghai')::date $$),active:=true);
end $block$;
update public.automation_jobs set schedule_text='每天17:00（北京时间；Asia/Shanghai；日终研究快照）',updated_at=now()
where job_code='daily_research_pipeline';
