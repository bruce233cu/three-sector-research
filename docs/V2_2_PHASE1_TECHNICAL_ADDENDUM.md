# A股主线识别系统 V2.2 Phase 1 工程补充合同

## 1 适用范围

本补充合同只固定 Phase 1 数据底座的工程实现，不修改 V2.2 已冻结的 S0 至 S4、指标公式、候选与确认规则、转弱与退潮规则、PIT 原则、冻结原则和机器与 AI 职责边界。发生冲突时，以 V2.2 原文为准。

## 2 标识规范

### 2.1 security_id

A 股证券使用带交易所后缀的永久代码，例如 `600000.SH`、`000001.SZ`、`920000.BJ`。证券退市后不删除、不回收、不改写 security_id。代码迁移或市场变更以别名表或修订记录处理，不覆盖历史主键。

### 2.2 taxonomy_id 与 object_id

`taxonomy_id` 是数据库 UUID，只用于关系和外键。`taxonomy_code` 保存来源原始代码，例如 `801750.SI`。申万一级 `object_id` 固定为 `sw1_` 加去除后缀的六位代码，例如 `801750.SI` 对应 `sw1_801750`。同一 taxonomy 版本变化保留新记录，不覆盖旧版本。

### 2.3 company_id 跨模块映射

现有三大赛道 `public.companies.id` 保持不变。Phase 1 不写复杂联动，只允许通过 `mainline.company_security_map` 保存 `company_id`、`security_id`、有效期、来源和置信状态。映射不清时保持空缺，不按名称猜测。

## 3 PIT 历史行业成分

某交易日成员必须同时满足：`effective_from <= trade_date`、`effective_to is null or effective_to >= trade_date`、`available_at <= calculation_cutoff`。`in_date/out_date` 只有在来源可证明其历史完整性时才能转成 strict PIT。当前截面、回溯补全或无法证明当时可得的数据一律标记 `historical_partial`，禁止写成 strict PIT。

退市证券继续保留在 `security_master` 和历史 Universe。停牌证券仍属于成员，但无有效行情时从相应指标有效分母排除并降低 coverage。PIT 导入必须保存 `source_version`、`fetched_at`、`available_at` 和 `source_snapshot_id`。

## 4 复权与公司行为

原始 OHLCV 与复权因子分表保存。收益计算不得使用在当时尚未可得的未来公司行动。复权因子记录 `effective_date`、`announced_at`、`available_at`、来源版本和快照。Provider 无法证明 PIT 时，记录 `data_quality_warning=non_pit_adjustment`，相关历史结果不得进入 strict PIT 验收。未知复权因子保持 NULL，不填 0 或 1。

## 5 Provider 标准 Schema

Provider 返回 `ProviderBatch`：`dataset`、`frame`、`source_id`、`source_version`、`fetched_at`、`available_at`、`run_id`、`request_fingerprint`、`historical_capability`。字段验证在 Provider 出口执行，缺列、类型不兼容或应有数据为空时抛标准异常，不静默补默认值。

核心数据集最小字段：

| 数据集 | 最小字段 |
|---|---|
| trading_calendar | exchange, cal_date, is_open, pretrade_date |
| security_master | security_id, ts_code, name, exchange, list_date, delist_date |
| daily_bars | security_id, trade_date, open, high, low, close, volume, amount, pct_chg |
| daily_valuation | security_id, trade_date, circ_mv, total_mv, turnover_rate |
| taxonomies | taxonomy_type, taxonomy_code, taxonomy_name, taxonomy_version, effective_from |
| membership_history | security_id, taxonomy_code, effective_from, effective_to |
| index_daily | index_id, trade_date, open, high, low, close, volume, amount |

## 6 Primary 与 Backup 映射

Primary 使用 Tushare：`trade_cal`、`stock_basic`、`daily`、`daily_basic`、`index_classify`、`index_member_all`、`index_daily`。凭据只从 `TUSHARE_TOKEN` 读取。

Backup 使用 AKShare 或其明确底层公开接口。Backup 必须逐数据集声明能力；不支持历史 PIT 的当前行业成分接口必须返回 `backup_unavailable=true`，不得降级冒充。日线、交易日历和指数若字段、日期和来源可追溯，可以单独作为该数据集 Backup；一个数据集可用不代表全部数据集可用。

## 7 重试与 Fallback

生产退避固定为 2 秒、5 秒、15 秒，共三次重试。测试可以注入零等待。Primary 超时、网络错误、标准 Schema 失败或应有数据为空时进入 Backup。Fallback 编排器而非 Provider 决定切换。最终保存 `source_used`、每次 attempt、标准错误、开始结束时间和结果行数。

Primary 与 Backup 同时成功时按字段容忍度比较。超过阈值写 `source_conflict_flag=true`。A级核心数据发生重大冲突时冻结，不自动择优覆盖。

## 8 时间与版本字段

- `source_version`：来源发布版本、接口版本或可复现的数据批次标识，不能为空。
- `fetched_at`：系统实际抓取时间，UTC timestamptz。
- `available_at`：该数据在外部世界最早可用时间；未知时不得反推为事件日期。
- `run_id`：一次采集或质量检查运行 UUID。
- `recompute_run_id`：因修订重新计算时的新 UUID，必须关联原始 run。

## 9 修订与幂等

原始快照 append-only。发现错误时新增修订记录和 source snapshot，不删除旧快照。相同业务键、来源版本和响应校验和重复执行不得新增重复数据。日线业务键为 `security_id + trade_date + source_id + source_version`；成分业务键为 `security_id + taxonomy_id + effective_from + source_id + source_version`。

重算必须生成新 `recompute_run_id`，保留原始 `run_manifest`。历史机器判断不得无痕覆盖。

## 10 数据冲突容忍度

价格绝对差异容忍度 0.01 元且相对差异 5bp；成交额相对差异 50bp；市值相对差异 100bp；交易日历、证券代码、成分有效期不允许语义冲突。阈值只用于来源一致性，不参与 S0 至 S4 业务判断。

## 11 Freeze 规则

A级数据包括交易日历、证券主数据、日线和 PIT 成分。最近交易日应有证券中成功行情完整率低于 95%、A级双源失败、严重来源冲突、Schema 漂移或 PIT 倒灌时：`critical_data_ok=false`、`stage_frozen=true`，并保存明确 `freeze_reason`。冻结只阻止新状态变化，不伪造数据。

## 12 测试 fixture

Fixture 仅用于测试，不写生产数据库，不作为真实验收统计。必须注明 `fixture=true`、虚构代码空间、固定时钟和预期结果。Fallback fixture 必须模拟 Primary 三次失败再由 Backup 接管。PIT fixture 必须包含调入前、调入后和调出后三个时间点。

## 13 run_manifest

每次运行保存：`run_id`、`recompute_run_id`、`job_name`、`as_of_date`、代码 commit、rule_version、profile_id、Provider 版本、source_snapshot_ids、参数哈希、开始结束时间、状态、行数、质量结果、冻结原因、错误摘要和父运行。清单 append-only。

## 14 环境变量合同

允许变量：`SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`TUSHARE_TOKEN`、`MAINLINE_PROVIDER_TIMEOUT_SECONDS`、`MAINLINE_LOG_LEVEL`。密钥不得进入浏览器、代码、提交、日志或测试快照。启动时只记录变量是否存在，不记录值。

## 15 GitHub 与 Sites 同步

GitHub `bruce233cu/three-sector-research` 是唯一 Source of Truth。开发分支必须从 GitHub main 创建并保留共同祖先。Sites 本地历史只作为来源审计，不迁移、不 force push。流程固定为 GitHub 分支开发、测试、提交，再同步到 Sites 部署 remote。Phase 1 不修改前端访问方式，也不把 `mainline` schema 暴露给浏览器。

## 16 Phase 1 Gate 表述

工程、数据库、Repository、质量、Fallback、Freeze 和测试完成，但严格历史申万 PIT 来源受外部权限或能力限制时，Phase 1 可以完成工程交付，G1 必须判定“部分通过”，并把历史 PIT 数据源列为主要阻塞项。禁止用当前成员回填历史或把 partial PIT 标成 strict PIT。
