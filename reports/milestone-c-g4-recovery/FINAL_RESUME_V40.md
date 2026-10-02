# A股主线识别系统 V2.2.1 — MILESTONE C FINAL CLOSE / G4 FINAL 交付包

日期：2026-10-02，Asia/Shanghai。状态：**G4 = FAIL；MILESTONE C = OPEN**。

前三项验收沿用：G1/G2/G3 = PASS，MILESTONE A/B = CLOSED。
PRODUCTION_MAINLINE_ENABLED = false，MAINLINE_LIVE = false。未进入 MILESTONE D。

## 代码与断点审计

| 项目 | 核查结果 |
|---|---|
| 指令指定起始 SHA | 33e615c39fec195a170b4dbfb932095c47de4824 |
| 本轮实际远端起点 | 7f8829861887d142151795082d8f2d5cd3412627 |
| 起点差异 | 前次恢复已提交读数、调度及 checkpoint 修复和 FAIL 报告；复用而未重复实施 |
| 本轮代码 SHA | 1234cf4b443fbe03d4be0ed062d1794794d331aa |
| 最终 SHA | 本交付包文件所在提交；精确值由 GitHub 提交响应和本轮交付消息提供 |
| 分支 | bruce233cu/three-sector-research / mainline-phase1e |
| 未提交工作 | 新建 checkout 起始干净；本轮修改均提交到该分支 |
| 范围保护 | 未修改 GitHub main，未 force push，未重写历史；未重跑 G1/G2/G3、五日 simulation、Provider 或 Universe |
| 原始数据 | 数据库仍保存指定五日共155条快照；正式生产成功日为空 |

本轮提交：
- 7c6841ca5b55e6cecef5568a46554ce08ca216c0：阻止缓存 simulation 快照被直接记为生产成功。
- 640cca2cc5e1530aba5e735e5d5e6d99b74561dd：新增生产成功边界的4项针对性测试。
- 1234cf4b443fbe03d4be0ed062d1794794d331aa：补齐状态条件、真实指标逐日对照和状态接口字段。
- 本文件所在提交：保存最终交付及真实阻塞状态。

## 本轮修复与发布

生产脚本的同日快照复用原先仅检查31条已存快照，可能把 simulation 当成 production 成功。
现在 production 快速复用还必须有**该日已有正式 production 成功记录**。
只有 simulation 快照时，不走“已成功”捷径；进入正常计算与原子提交链。
测试明确检查“尚无正式成功”“只有前一日成功”“已有同日正式成功”和“simulation正常复用”四种情况，全部通过。测试中的故障注入未产生真实业务写入。

前端继续使用现有 /api/mainline：
- 首页和雷达读取真实快照、S0–S4分布、冻结与状态变化。
- S1展示候选日期、候选规则及确认连续计数和未满足条件。
- S2展示确认日期、确认条件、成交强度与相对强弱。
- S3展示转弱日期、条件及恢复规则和连续计数。
- S4展示退潮日期、生命周期起止、最高状态及已保存的重入计数。
- 详情增加真实指标逐日对照；沿用真实状态时间轴、规则证据、质量、生命周期与来源。
- 状态 API 补齐 current_milestone、milestone_status、latest_code_sha、G1–G4及根层S0–S4计数。
- latest_code_sha 来自最近业务尝试的 manifest，故当前仍为33e615c…，不冒充最新前端部署代码。
- 没有新增第二套 API、第二个网站或 AI 状态判断。

| 发布项目 | 结果 |
|---|---|
| Sites版本 | 40 |
| Sites源码提交 | 77bfc74c1d41ddbdb47102be72e75d8f112292f5 |
| 对应GitHub业务代码 | 1234cf4b443fbe03d4be0ed062d1794794d331aa |
| 部署 ID | appgdep_6abf6b6aa4788191b12ffda9c54afda1 |
| 部署结果 | succeeded |
| 站点 | https://sanda-saidao-research.zdrzdrzdr233cu.chatgpt.site/mainline |
| 登录与分享 | 原访问边界保留；未使用绕过令牌 |
| Edge Function | mainline-status v5、mainline-production-gateway v3、v43-daily-pipeline v19；本轮未重复部署 |
| Supabase变化 | 未新增/改动核心schema、业务快照和筛选规则；仅追加系统优化记录并查询确认 |
| 优化记录 | mainline-g4-final-resume-v40-20261002；验收结果“未通过” |

Sites与GitHub使用不同托管源码仓库，SHA分别列出。发布源从已有Site准确打开，仅同步本轮三个前端文件，不改三大赛道页面与业务逻辑。

## G4逐项验收及边界

| 验收项 | 结果与证据边界 |
|---|---|
| /mainline真实snapshot、radar | 已部署Edge返回2026-09-30、31行业；构建后的实际Worker路由也返回200和31行业 |
| S0–S4分布 / Frozen | 9 / 14 / 1 / 2 / 5，Frozen=1；来自实际数据库 |
| S1–S4展示 | 真实rows筛选，专门状态条件和生命周期已加入页面；登录后点击检查单列人工项 |
| sector detail | 实际API返回1个行业，详情采用真实状态与指标 |
| timeline / metric history | 轻工制造10个已持久化日期；趋势直接使用timeline中的真实metrics |
| rule evidence | 轻工制造53条真实证据；未使用AI生成硬状态 |
| data quality / source lineage | 数据库和Edge输出真实质量、来源、版本、checksum；NULL不填0 |
| status API | 版本V2.2.1、MILESTONE C、Gate、生产开关、三类日期、运行状态、业务代码SHA和计数可读取 |
| latest success | 正式生产为空；simulation=2026-09-30。沿用既有失败不覆盖最近成功逻辑与证据 |
| simulation / production | 独立标签，生产未启用；新增防止simulation直接晋升production成功的测试 |
| scheduler / Workflow | inputs含pipeline_run_id/business_date/run_type；现有0 9 * * *对应17:00 Asia/Shanghai，保持不变 |
| pipeline_run_id链 | 代码链和既有数据库父子追踪测试通过；真实后台dispatch链仍因凭据缺失未认证 |
| dispatch与业务成功 | 保留dispatched/running/succeeded/partial/failed语义；dispatch不算业务成功 |
| mainline / three-sector独立 | 复用既有父子任务隔离和迟到回写测试；三大赛道逻辑未改 |
| 最新DB checkpoint | 实查后续日期context选择2026-09-30、31个checkpoint、9517条板块warm history，bootstrap_source=database_checkpoint |
| 版本兼容 | 沿用已验证taxonomy/rule/profile/metric availability匹配及不完整、非法计数器拒绝逻辑 |
| continuation实际计算 | 复用此前真实2026-09-29→2026-09-30的9项通过证据；本轮未重跑。自然后续交易日为2026-10-08，当前尚未来到，不能伪造9月30日之后计算结果 |
| 断点幂等 / lifecycle | 复用既有同日idempotent、checkpoint内容及lifecycle数量不变的数据库证据 |
| backfill安全 | 复用既有冲突checksum拒绝和写库故障回滚证据；不改历史或latest success |
| API测试 | 已部署Edge summary/detail=200；新构建Worker summary/radar/detail/page均200；详情10日期/53规则 |
| Sites build | GitHub checkout和Sites准确发布源码均构建通过 |
| 前端binding / UI | 构建路由实际连接真实Supabase结果；正常登录后的标签切换和抽屉点击尚需MANUAL_UI_CHECK_REQUIRED |
| three-sector回归 | 18项Node调度/UI合同测试通过，保护现有三大赛道业务 |
| 新增生产边界测试 | 4项Python测试通过；不计为真实production执行 |
| Sites部署 | v40 succeeded；部署成功不当作浏览器交互证明或生产成功证明 |

已有checkpoint兼容、幂等、backfill和父子隔离证据位于reports/milestone-c-g4-recovery/。
production simulation工作流36970118460和155条快照继续复用，不触发重跑。

## 当前真正Blocking Issue

**1. 每日自动派发凭据缺失。**

现场Edge readiness仍返回dispatch_credential_configured=false。
现有v43-daily-pipeline需要MAINLINE_GITHUB_DISPATCH_TOKEN，当前没有配置，因此无法认证：
Daily Pipeline → GitHub Workflow → production script → business manifest → checkpoint/snapshot的真实后台链。

本轮可调用的Supabase工具不提供设置函数Secrets的操作；连接器的授权不等于可供后台长期使用的GitHub派发凭据。
不能用连接器私有token填充后台，也不能用一次手动Workflow运行冒充已修好每日scheduler。
因此G4仍FAIL，生产开关不启用。

**MANUAL_UI_CHECK_REQUIRED**单独保留：正常登录后核对页面标签、行业抽屉和指标历史。依照用户要求，它不是单独判G4失败的原因。

## 最小后续动作

1. 在GitHub创建限定three-sector-research仓库的fine-grained token，Actions权限选Read and write。
   官方权限依据：https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
2. 在项目函数Secrets保存为MAINLINE_GITHUB_DISPATCH_TOKEN：
   https://supabase.com/dashboard/project/pdtlzleqsoftuxdnbdey/functions/secrets
   不把token粘贴进聊天、源码、报告或数据库业务记录。
3. 配置后先重新读取readiness，再执行最小真实dispatch和数据库完成回写验收；不重跑五日simulation。
4. 验证最新兼容checkpoint续跑、父子状态和latest success；在全部Gate要求通过后再关闭G4及启用mainline_job。
5. 真正有production成功日以后才输出LIVE；否则保持simulation或ready_waiting_first_production_run。

## 技术债

- 登录后的生产页面点击验证尚未完成。
- 自然后续交易日尚未到来，本轮不提供未来交易日计算证明；保留真实历史隔离续跑证据。
- 派发凭据配置和实际后台dispatch是下一轮唯一外部配置阻塞。
- 大型summary携带完整规则证据，后续可优化响应体；本轮不新建API或扩大范围。
- 更完整的跨生命周期历史图表可后续完善；当前展示真实已持久化日期，不补造历史。

本轮没有输出MILESTONE D开工清单，因为G4尚未PASS。
