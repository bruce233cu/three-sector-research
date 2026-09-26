insert into public.system_optimization_records (
  record_key, version, record_date, change_types, one_line_summary, why_changed,
  problems_found, main_changes, expected_result, database_changed, database_change_summary,
  screening_logic_changed, screening_logic_summary, automation_changed, automation_change_summary,
  old_data_impact, acceptance_result, unresolved_issues, next_step, important_decisions,
  technical_details, is_version_summary
) values (
  'mainline-v2-2-phase1-data-foundation', 'V2.2 Phase 1', '2026-09-26',
  array['数据库','数据源','数据质量','工程治理'],
  '在现有三大赛道系统中增加隔离的A股主线数据底座，不改变既有业务和冻结规则。',
  '主线模块需要可追溯的PIT数据、主备Provider、质量冻结和运行审计，不能使用当前成分回算历史。',
  '["运行环境缺少TUSHARE_TOKEN","严格申万一级历史PIT尚未获得合格数据源","AKShare宽基指数接口存在间歇失败"]'::jsonb,
  '["新增mainline私有schema及17张表","实现Tushare/AKShare统一Provider合同","实现PIT查询仓库、质量阈值、Fallback和Freeze","保存冻结parameter_profile及Provider登记","真实写入AKShare交易日历和来源审计"]'::jsonb,
  '为后续指标和状态机提供可审计的数据底座；核心数据异常时冻结，不生成伪状态。',
  true,
  '新建mainline schema，浏览器角色无访问权；现有public业务表未改造。',
  false,
  'S0-S4、指标、候选/确认/转弱/退潮规则均未修改，Phase 2未开始。',
  true,
  '增加Provider重试/回退、质量检查、Freeze及运行审计基础。',
  '现有三大赛道数据和页面不受影响；主线业务表除配置和已验证交易日历外未填充。',
  '部分通过',
  '["取得合格的申万一级历史PIT成员数据","配置并验证TUSHARE_TOKEN","验证或替换不稳定的宽基指数Backup","完成2019年至今全量行情与流通市值回放"]'::jsonb,
  '先补齐严格PIT和Primary真实验证，通过G1后再进入Phase 2。',
  '["GitHub main不重写，开发分支从当前main创建","Sites SHA仅作来源审计，不迁移本地历史","mainline schema不暴露浏览器","不合格Backup显式标记backup_unavailable"]'::jsonb,
  jsonb_build_object(
    'sites_source_audit_sha','67b8f9563da3449c6d1c1d123895e5a5cb2d108e',
    'github_main_sha','938fa5b8e4ed6ea7336617b1067ab2e5a9876743',
    'github_lineage_baseline_sha','e48b6ca863175dd601436b1eef10c2e0c4fa0388',
    'schema','mainline','tables',17,'python_tests',16,'site_tests',11,
    'real_backup','AKShare 1.18.97 trading calendar','strict_pit',false
  ),
  true
)
on conflict (record_key) do update set
  version=excluded.version, record_date=excluded.record_date, change_types=excluded.change_types,
  one_line_summary=excluded.one_line_summary, why_changed=excluded.why_changed,
  problems_found=excluded.problems_found, main_changes=excluded.main_changes,
  expected_result=excluded.expected_result, database_changed=excluded.database_changed,
  database_change_summary=excluded.database_change_summary,
  screening_logic_changed=excluded.screening_logic_changed,
  screening_logic_summary=excluded.screening_logic_summary,
  automation_changed=excluded.automation_changed,
  automation_change_summary=excluded.automation_change_summary,
  old_data_impact=excluded.old_data_impact, acceptance_result=excluded.acceptance_result,
  unresolved_issues=excluded.unresolved_issues, next_step=excluded.next_step,
  important_decisions=excluded.important_decisions, technical_details=excluded.technical_details,
  is_version_summary=excluded.is_version_summary;
