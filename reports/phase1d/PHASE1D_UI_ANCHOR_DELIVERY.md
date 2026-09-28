# 《A股主线识别系统 V2.2 — Phase 1D + UI Anchor 联合交付报告》

报告日期：2026-09-28  
模块：现有“三大赛道高赔率研究系统”内的一级模块  
开发分支：`mainline-phase1d`  
Phase：Phase 1D  
Gate：G1  

## 交付结论

- **G1：部分通过**
- **Phase 1D：部分通过**
- **是否允许进入 Phase 2：否**
- 原因：一级入口、真实状态页、板块定义与 effective PIT、按需行情、板块结果持久化和审计链已经形成；但真实客观指标仅 **4/15** 样本达到非冻结成功标准，低于既定的 **12/15** 最低线。其余 11 个样本均因成分股窗口数据覆盖不足被冻结，不能宣传为闭环通过。

## A. UI Anchor 验收

### 1—8. 页面与导航

| 验收项 | 结果 | 可核查证据 |
|---|---|---|
| 一级入口“A股主线” | 已实现，待本报告对应版本完成 Sites 部署后做线上最终确认 | `app/research-ui.tsx` |
| `/mainline` 路由 | 已实现 | `app/mainline/page.tsx` |
| 独立代码边界 | 通过；未塞入通用动态模块页 | `app/mainline/`、`app/api/mainline/` |
| 页面当前阶段 | 从真实接口显示 V2.2 / Phase 1D / G1 / 部分通过 | `supabase/functions/mainline-status/index.ts` |
| 样本统计 | 从数据库读取，不写死：总计15、成功4、PARTIAL 11、FAIL 0、运行中0 | `public.get_mainline_phase1d_status()` |
| 数据健康 | 展示历史定义、历史成员、行情、市值、缓存、Freeze、最近 run | `/mainline` 数据健康区 |
| 最近板块样本 | 展示真实日期、行业、代码、成员、有效成员、覆盖率、收益、RS10、Freeze | `mainline.daily_mainline_snapshot` |
| 假数据 | 无；缺失值显示“数据不足/待计算”，没有以0代替未知 | 页面适配器与数据库快照 |

页面明确写明：本模块只识别市场和板块；公司利润、估值、赔率和投资价值属于三大赛道深度研究，不在本模块计算。

## B. Phase 1D 板块级 POC

### 9—18. 15个样本最终状态

统一 run_id：`8e59047b-0346-547e-a036-db09b21377ce`  
结果口径：`critical_data_ok=true` 且 `stage_frozen=false` 才计 SUCCESS；否则计 PARTIAL。没有把“生成了一行记录”误计为成功。

| 日期 | 行业 | 代码 | 分类版 | 成员/有效 | 覆盖率 | 状态 | Freeze | 补跑耗时 |
|---|---|---:|---|---:|---:|---|---|---:|
| 2019-06-28 | 电子 | 801080 | SW2014 | 189/0 | 0.00% | PARTIAL | 是 | 200秒 |
| 2019-06-28 | 食品饮料 | 801120 | SW2014 | 33/32 | 96.97% | SUCCESS | 否 | 历史审计未记录 |
| 2019-06-28 | 非银金融 | 801790 | SW2014 | 50/0 | 0.00% | PARTIAL | 是 | 196秒 |
| 2020-06-30 | 有色金属 | 801050 | SW2014 | 118/0 | 0.00% | PARTIAL | 是 | 198秒 |
| 2020-06-30 | 食品饮料 | 801120 | SW2014 | 38/0 | 0.00% | PARTIAL | 是 | 154.461秒 |
| 2020-06-30 | 非银金融 | 801790 | SW2014 | 53/11 | 20.75% | PARTIAL | 是 | 179.398秒；保留覆盖更高的原结果 |
| 2021-12-31 | 电子 | 801080 | SW2021 | 361/0 | 0.00% | PARTIAL | 是 | 191.958秒 |
| 2021-12-31 | 银行 | 801780 | SW2021 | 42/41 | 97.62% | SUCCESS | 否 | 历史审计未记录 |
| 2021-12-31 | 机械设备 | 801890 | SW2021 | 472/0 | 0.00% | PARTIAL | 是 | 203.804秒 |
| 2023-06-30 | 有色金属 | 801050 | SW2021 | 141/0 | 0.00% | PARTIAL | 是 | 160.857秒 |
| 2023-06-30 | 食品饮料 | 801120 | SW2021 | 125/99 | 79.20% | SUCCESS | 否 | 175.844秒 |
| 2023-06-30 | 机械设备 | 801890 | SW2021 | 550/0 | 0.00% | PARTIAL | 是 | 290秒超时 |
| 2025-06-30 | 电子 | 801080 | SW2021 | 491/0 | 0.00% | PARTIAL | 是 | 185.300秒 |
| 2025-06-30 | 银行 | 801780 | SW2021 | 42/42 | 100.00% | SUCCESS | 否 | 历史审计未记录 |
| 2025-06-30 | 机械设备 | 801890 | SW2021 | 600/226 | 37.67% | PARTIAL | 是 | 200秒；保留覆盖更高的原结果 |

最终统计：**SUCCESS 4、PARTIAL 11、FAIL 0、运行中 0、Freeze 11**。

### 指标与 NULL/Freeze

- 生成的客观字段包括板块收益、基准收益、RS5/10/20、成交指标、上涨比例、MA20/MA60覆盖、60日新高、Top3成交集中度、Top3收益贡献及逐指标覆盖率。
- 覆盖不足时相应指标保持 `NULL`；没有把未知数据写成0。
- Freeze阈值真实生效：11个低覆盖样本 `critical_data_ok=false`、`stage_frozen=true`，并保存具体 `freeze_reason`。
- `hard_status` 保持 `NULL`；未执行 S1/S2/S3/S4，也未伪造 S0。

### PIT、来源、缓存与重跑

- 15/15 样本达到 `effective_pit`：使用满足 `effective_from <= T` 且 `effective_to is null or effective_to >= T` 的成员关系。
- 0/15 达到 knowledge-time strict PIT；均如实记录 `knowledge_time_unverified=true`，没有将 effective PIT 冒充严格知识时点盲测。
- 区分 SW2014 与 SW2021，不以2021版分类回填2019/2020。
- 数据来源：申万官方分类与行业指数接口、东方财富K线、网易历史CSV、BaoStock历史行情备用源。
- 主要故障：BaoStock登录返回 `10002007: 网络接收错误`；东方财富/网易对部分历史证券窗口恢复率不足。2023-06-30有色金属失败在成分股行情窗口，不是成员获取或字段适配失败。
- 个股窗口仅进入 Parquet/DuckDB临时缓存；缓存审计行数36,297，写入Supabase逐股历史行数为0。
- 3个样本以相同来源版本、参数和代码重复计算，校验结果一致：`rerun_identical=true`。

可核查文件：

- `reports/phase1d/final-v2/sector_snapshots.json`
- `reports/phase1d/final-v2/poc_summary.json`
- `reports/phase1d/final-v2/run_manifest.json`
- `reports/phase1d/final-v2/source_snapshots.json`
- `reports/phase1d/final-v2/membership_evidence.json`
- `reports/phase1d/final-v2/anomaly_tests.json`
- `reports/phase1d/final-v2/calculation_traces.json`

## C. 串线检查

### 19—22. 三大赛道生产数据影响

此前误入本轮上下文的任务是原系统正常收盘链，不属于 Phase 1D。查询到2026-09-28写入：

| 表/对象 | 行数 | 判定 |
|---|---:|---|
| `price_snapshots` | 8 | 原系统正常收盘价任务 |
| `expected_return_snapshots` | 3 | 原系统正常重算任务 |
| `company_daily_snapshots` | 3 | 原系统正常每日快照 |
| `investment_assessments` | 3 | 原系统正常门槛评估 |
| `probability_changes` | 0 | 未发生价格驱动概率变更 |
| `company_timeline_events` | 0 | 未产生错误关键节点 |

处理决定：**不回滚**。这些是可追溯的原系统正常收盘结果，删除反而会破坏原系统历史；统一标记为“非Phase 1D结果，不纳入本轮验收”。本轮此后没有继续写公司利润、概率、估值、赔率、研究池或公司时间轴。隔离措施包括独立 `src/mainline`、独立 `/mainline`、独立 mainline schema、失败样本专用工作流。

## D. 工程交付

### 23. GitHub

- 仓库：`bruce233cu/three-sector-research`
- 分支：`mainline-phase1d`
- UI/重试基线Commit：`af530d0e95fbf7ee902bf8391d51c5b860b1c2cb`
- 本报告、最终审计结果和“保留更强真实快照”的聚合修正将由本次最终提交承载；以交付消息中的最终 SHA 为准。
- 失败补跑Workflow：<https://github.com/bruce233cu/three-sector-research/actions/runs/36411633805>
- 基线CI：<https://github.com/bruce233cu/three-sector-research/actions/runs/36411633812>（通过）

### 24. 测试与CI

- Python自动测试：33 PASS、0 FAIL、0 SKIP。
- Node自动测试：14 PASS、0 FAIL、0 SKIP。
- Production build：通过；构建路由包含 `/mainline` 与 `/api/mainline`。
- 新增聚合回归测试保证失败重试不能覆盖覆盖率更高的既有真实结果。

### 25. Sites

- 现有站点项目：`appgprj_6a9fc01749888191aa90eb53087f13de`
- 现有地址：<https://sanda-saidao-research.zdrzdrzdr233cu.chatgpt.site>
- 本报告完成时将部署同一站点、保留现有访问控制，并实际访问 `/mainline` 验证；最终版本号与线上验证结果以交付消息为准。

### 26. Supabase

- 项目：`pdtlzleqsoftuxdnbdey`
- 新增 `mainline.phase1d_sample_runs`：保存15个样本状态、耗时、错误与运行审计。
- 新增只读状态RPC `public.get_mainline_phase1d_status()`：只向服务端状态函数授权，不开放 mainline schema 给浏览器。
- 部署 `mainline-status` Edge Function：只读、发布密钥校验、服务端查询真实状态。
- `mainline.daily_mainline_snapshot` 保存15条板块级客观结果；不写逐股全量历史；`hard_status` 为NULL。
- 数据库状态接口已实测返回：4 SUCCESS、11 PARTIAL、0 FAIL、11 Freeze、最近run_id=`8e59047b-0346-547e-a036-db09b21377ce`。

## G1检查表

- [x] 历史板块定义可取得
- [x] 历史板块成员可按日期取得
- [x] effective PIT通过
- [x] 未使用未来成分
- [x] 成分股所需窗口可按需取得（但稳定性和覆盖率未达标）
- [ ] 5日期×3行业中至少12个真实样本成功（当前4/15）
- [x] 板块客观指标在有效样本中正确生成
- [x] coverage正确记录
- [x] 缺失值不填0
- [x] Freeze真实有效
- [x] 来源与source snapshot可追溯
- [x] run_manifest可追溯
- [x] 3个样本重跑一致
- [x] 不依赖全A永久历史仓库
- [x] 未开发Phase 2状态判断

## 最终决定

**G1：部分通过**  
**Phase 1D：部分通过**  
**是否允许进入Phase 2：否**

下一步只应修复历史成分股行情窗口的稳定数据源或合格备用源，并仅补跑当前11个PARTIAL样本；不得回到全A历史数据回灌路线，也不得提前开发状态机。
