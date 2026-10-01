export function successfulReports(rows: any[], pipeline: any) {
  const success = pipeline?.three_sector?.latest_success_report;
  if (!success) return [];
  // The successful frozen version wins even if a newer failed run wrote a row.
  return [success, ...rows.filter(row => row.report_date < success.report_date)];
}
export async function readDailyPipeline() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) throw new Error('Supabase runtime configuration is missing');
  const read = async (path: string) => {
    const response = await fetch(`${url}/rest/v1/${path}`, {headers:{apikey:key,Authorization:`Bearer ${key}`},cache:'no-store',signal:AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error(`Daily result reader unavailable: ${response.status}`);
    return response.json();
  };
  const common='automation_runs?select=id,run_date,status,started_at,finished_at,metadata&job_code=eq.daily_research_pipeline';
  const [latestRows,successRows] = await Promise.all([
    read(`${common}&order=started_at.desc&limit=1`),
    read(`${common}&or=(metadata->jobs->three_sector_daily_job->>status.eq.succeeded,and(status.eq.succeeded,metadata->>daily_pipeline_version.is.null))&order=finished_at.desc.nullslast&limit=1`),
  ]);
  const latest=latestRows[0], success=successRows[0];
  let report=success?.metadata?.successful_report || null;
  if (success && !report) {
    const steps=await read(`automation_run_steps?select=metadata&run_id=eq.${success.id}&step_code=eq.daily_report_generation&status=eq.succeeded&limit=1`);
    const number=steps[0]?.metadata?.version_number;
    if (Number.isInteger(number)) {
      const versions=await read(`daily_report_versions?select=*&report_date=eq.${success.run_date}&version_number=eq.${number}&generated_at=gte.${encodeURIComponent(success.started_at)}&generated_at=lte.${encodeURIComponent(success.finished_at)}&limit=1`);
      if (versions[0]) {
        const version=versions[0];
        const rows=await read(`daily_reports?select=*&id=eq.${version.report_id}&limit=1`);
        if(rows[0]) report={...rows[0],frozen_snapshot:version.frozen_snapshot,generated_at:version.generated_at,report_version:version.report_version};
      }
    }
  }
  return {timezone:'Asia/Shanghai',three_sector:{latest_success_at:report ? success.finished_at : null,latest_success_report:report,latest_run_status:latest?.metadata?.jobs?.three_sector_daily_job?.status || latest?.status || null,latest_run_date:latest?.run_date || null},mainline:latest?.metadata?.jobs?.mainline_job || {status:'skipped',reason:'pending_provider',provider_enabled:false}};
}
