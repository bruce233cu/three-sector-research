# V2.2 Phase 1C 数据源可行性报告

- 项目：A股主线识别系统 V2.2（现有“三大赛道高赔率研究系统”的独立一级模块）
- 阶段：Phase 1C — 数据源攻关与最终数据方案确认
- 报告日期：2026-09-26
- 施工边界：仅研究和确认数据源方案；未开发 RS、WIN、TURNOVER、Breadth、S1-S4、状态机、前端、AI解释、结构标签或市场环境
- 当前 Gate：G1 部分通过；本报告不授权进入 Phase 2
- 环境事实：本次运行环境未检测到 `TUSHARE_TOKEN`，因此没有把文档可用性冒充为真实 API 调用成功

## 一、结论先行

### 1.1 总结判断

1. **Tushare 只能判定为“部分可以作为完整 Primary”**。
   - 对交易日历、证券主数据、A股日线、每日指标/流通市值、常见宽基日线，接口覆盖和成本都较合适。
   - 对申万分类定义和带 `in_date/out_date` 的成员关系，能够提供很有价值的候选数据。
   - 但仅凭 `index_member_all` 不能关闭 strict PIT：它没有逐条公开的历史发布日期/首次可得时间，且公开 issue 已出现成员区间断档和历史分类语义不清的案例。
   - `index_daily` 官方说明不包含申万指数行情，且公开 issue 存在区间缺失与更新滞后报告。
2. **G1 的最大剩余问题不是“有没有历史字段”，而是“能不能证明某个历史时点当时已经知道这些成员关系”**。
3. **最快且可靠的路线是：Tushare 负责基础数据；付费专业源或经合同验证的历史成员源负责申万 strict PIT；申万官方公告/样本文件负责权威复核与版本留档。**
4. **低成本可行路线是：Tushare 5000 积分 + 理杏仁/聚宽指定日期成员查询 + 申万官方公告归档。** 但在完成 2019、2020、2021、2023、2025 五个日期抽查和至少一只股票调入/调出三段验证前，仍只能标为 `historical_partial`。
5. **纯免费路线可以继续做工程和 partial PIT 研究，但不应宣布 G1 strict PIT 通过。**

### 1.2 strict PIT 的最低证据标准

对每条行业成员关系，至少同时需要：

| 维度 | 必须有 | 说明 |
|---|---:|---|
| 关系生效 | `effective_from` | 成员从何日开始属于该行业 |
| 关系失效 | `effective_to` | 成员从何日不再属于该行业 |
| 当时可知 | `available_at` / `announced_at` | 系统最早何时能够合法知道该关系 |
| 版本 | `source_version` | 申万2014版、2021版或具体发布批次 |
| 原始快照 | `source_snapshot_id` | 文件哈希、公告ID或供应商快照ID |
| 可追溯来源 | URL/供应商记录 | 可复查原始公告或数据快照 |

只有 `in_date/out_date`，但没有发布日期、版本和历史快照，属于“有效期历史”，**不等于**“严格的当时可知历史”。

---

## 二、Tushare 七个接口真实能力判断

Tushare Pro 所有接口均需要用户 Token；积分是年度权限门槛，不按调用消耗。2026 年官方价格表显示：个人 2000 积分为 200 元/年、5000 积分为 500 元/年；机构价格为个人价的 10 倍。积分和价格应以购买当日官方页面为准。

| 接口 | Token | 权限门槛 | 2019年至今 | 退市覆盖 | 历史回放判断 | 对 strict PIT 的作用 | 结论 |
|---|---:|---:|---|---|---|---|---|
| `trade_cal` | 需要 | 2000 积分 | 结构上支持 | 不适用 | 可按交易所和日期查询；应实测完整性 | 可定义交易日，但没有解决行业成员当时可知性 | 可作 Primary，待 Token 实测 |
| `stock_basic` | 需要 | 2000 积分 | 当前快照含上市/暂停/退市状态及上市、退市日期 | 可通过 `list_status=D` 请求 | 可构建含历史退市证券的主数据；仍需真实总量核对 | 主数据不是 PIT 行业成员证据 | 可作 Primary，待 Token 实测 |
| `daily` | 需要 | 120 起；高频回放建议 2000/5000 | 官方称“全部历史” | 证券存在期间可查；停牌日无行情 | 单股请求上限足以覆盖长历史，也可按交易日循环全市场；必须核对停牌与退市尾部 | 不适用 | 可作行情 Primary |
| `daily_basic` | 需要 | 2000 起；5000 频次更适合回放 | 文档允许按交易日循环历史 | 理论上随历史证券 | 含总股本、流通股本、总市值、流通市值；需要实测修订和缺口 | 不适用 | 可作市值 Primary，待覆盖率验收 |
| `index_classify` | 需要 | 2000 积分 | 提供申万2014版和2021版分类定义 | 不适用 | 可建 taxonomy；不是分类发布事件日志 | 可保存版本定义，但不足以证明历史成员 | 可作 taxonomy Primary |
| `index_member_all` | 需要 | 2000 积分 | 接口设计有 `in_date/out_date` | 示例包含退市股票 | 字段结构支持有效期回放；公开 issue 存在 2018-2022 成员区间断档和分类名称语义疑问 | 缺逐条 `announced_at/available_at`；不能单独判 strict | 只可作候选 Primary，必须交叉验证 |
| `index_daily` | 需要 | 2000；5000 提升频次 | 多类指数历史日线 | 不适用 | 官方明确不含申万指数；公开 issue 有部分指数区间缺失和更新滞后 | 不提供行业成员 PIT | 可作部分宽基 Primary，不可承担申万指数行情 |

### 2.1 历史缺口和事后回填风险

- `index_member_all` 的公开 issue（2026-09-12，仍开放）给出 000506.SZ：存在 2009-2015、2015-2018 记录后跳到 2022 的区间，用户无法判断 2018-06-15 至 2022-07-29 的分类；同时质疑 `in_date/out_date` 边界和历史名称是否被新版名称替换。这说明**字段存在不等于历史连续、版本语义正确**。
- `index_daily` 的公开 issue 报告过某指数 2022 年 1-10 月数据缺失，也报告过指数更新落后多个交易日。它适合进入自动质量检查，不适合无条件信任。
- `stock_basic`、`index_classify`、`index_member_all` 更像供应商当前维护的可变快照。若供应商事后修订历史，只有我们自己的抓取快照和哈希才能证明“当时返回过什么”。

### 2.2 available_at 的工程定义

| 数据集 | 建议 `available_at` 定义 | 能否回溯重建 |
|---|---|---|
| `daily` | 我方在官方更新窗口后首次成功抓取的时间 | 旧历史只能记本次抓取时间，不能伪装成历史当日可得 |
| `daily_basic` | 我方首次成功抓取并通过质量检查的时间 | 同上 |
| `stock_basic` | 我方快照抓取时间 | 不能从当前快照反推历史当时可得 |
| `index_classify` | 官方版本发布日期；缺失时用我方首次抓取时间并降级 | 需申万版本公告 |
| `index_member_all` | 对应申万调整公告发布时间；没有公告时仅记我方首次抓取时间并标 `historical_partial` | 仅凭 Tushare 无法完整重建 |
| `index_daily` | 供应商返回且通过完整性检查的首次抓取时间 | 可从现在开始可靠留痕，过去的知识时间不可倒推 |

---

## 三、strict PIT 申万历史成分候选源

| 候选源 | 2019至今覆盖 | 指定历史日期 | 调入/调出 | 发布/版本证据 | PIT可信度 | API/自动化 | 费用 | 本轮判断 |
|---|---|---|---|---|---|---|---|---|
| 申万指数官方 | 有分类文件、成分下载和调整公告；完整归档需逐年核验 | 通过历史公告/样本重建 | 公告可证明调整 | **最权威** | 高，但需把公告、文件和生效日拼成事件链 | 无统一公开稳定 API 证据；抓取和归档工作量高 | 页面公开；使用授权需核对 | strict PIT 的权威锚点，不宜单独承担高效批量回放 |
| Tushare `index_member_all` | 设计目标覆盖历史 | 可由 in/out 推导 | 有 | 缺逐条发布日期/历史快照 | 中；已有断档 issue | API 简单 | 2000积分起 | 适合作候选集，不可单源过 Gate |
| Wind | 官方宣称强历史回溯和全品种 API | 通常可做，需售前样例证明申万历史板块 | 需合同/样例确认 | 可要求供应商版本与时间字段 | 潜在最高 | 成熟 API | 高，当前价格需询价 | A方案首选之一；购买前必须做 5 日期样例验收 |
| Choice | 专业终端通常具备历史板块能力 | 需售前演示确认 | 需确认 | 需确认 | 潜在高 | 付费 API/终端 | 高，需询价 | 与 Wind 同级比选，不可只凭宣传采购 |
| 同花顺 iFinD | 文档存在指定日期指数成分能力 | 有潜力 | 需确认申万行业端点 | 需确认 | 中高，取决于合同字段 | 付费 API | 需询价 | 进入付费 POC 候选 |
| 聚宽 JQData | 官方说明支持 `get_industry_stocks(industry_code, date)`，并强调避免未来函数；文档还提示 2014 分类大调整 | 支持 | 多为按日快照，不一定直接给公告事件 | 通常无官方公告时间 | 中 | API 友好 | 试用/商业方案需当前询价 | 低成本交叉验证候选，不应单独证明 available_at |
| 理杏仁 | 官方开放 API 支持申万2021版在指定日期查询；文档明确 2021 年以前可能无数据 | 支持 | 由日期快照差分 | API 本身不返回公告时间 | 2021年后中高；2019-2020不足 | API 友好 | Token/套餐需当前询价 | 很好的第二校验源，但不能单独覆盖 2019 起全区间 |
| 米筐 Ricequant | 支持按历史日期取指数成分；申万行业指数数据可查 | 部分支持 | 需验证申万行业成员端点 | 未证明公告时间 | 中/未证实 | API | 套餐需询价 | 必须先做申万 L1 真实样例，未通过前不列合格 Backup |
| AKShare | 能抓取申万官网分类文件、指数和成分页面 | 取决于上游 | 取决于上游 | 自身不是原始来源 | 只等于其上游 | 免费、易受页面变化影响 | 免费 | 仅作传输适配器；不能把 AKShare 名称当数据来源 |
| 历史样本文件+调整公告 | 取决于档案是否齐全 | 可重建 | 有公告即可 | **强** | 高，若档案完整、文件哈希和发布时间齐全 | 自动化难度较高 | 公开/人工成本 | 免费方案中唯一有机会达到 strict 的路线，但必须完成档案审计 |
| 公开整理数据集 | 常见仅2020/2021后、月度或当前截面 | 部分 | 不稳定 | 通常弱 | 低至中 | 容易 | 免费/低价 | 只可做发现与对照，禁止作为 Gate 证据 |

### 3.1 最高优先级结论

strict PIT 最现实的来源不是某一个接口，而是：

> **专业历史成员数据（Wind/Choice/iFinD 经 POC 验证） + 申万官方调整公告/样本文件 + 我方不可变快照。**

如果预算有限，则：

> **Tushare `index_member_all` + 聚宽/理杏仁指定日期快照 + 申万官方公告复核。**

后者在所有历史断点和 `available_at` 证据没有补齐前，仍标 `historical_partial`。

---

## 四、三档数据源组合方案

### A方案：最可靠、允许付费

| 数据集 | Primary | Backup / 复核 | PIT质量 |
|---|---|---|---|
| 交易日历 | Wind/Choice/iFinD 经合同确认 | Tushare `trade_cal` + 交易所日历 | 高 |
| 证券主数据 | Wind/Choice/iFinD | Tushare `stock_basic` + 交易所退市名单 | 高 |
| 股票日线 | Wind/Choice/iFinD | Tushare `daily` | 高 |
| 流通市值 | Wind/Choice/iFinD | Tushare `daily_basic` | 高 |
| 行业定义 | 申万官方版本文件 | Tushare `index_classify` | 高 |
| 历史成分 | 专业源历史申万成员事件 | 申万官方调整公告/文件；Tushare 交叉检查 | **可达 strict，前提是 POC 验证发布时间/版本** |
| 宽基指数 | 专业源 | Tushare + 指数公司/交易所 | 高 |

- 费用：高；必须向 Wind、Choice、iFinD 询当前终端/API报价和再分发/存储授权，不采用网络旧报价做预算。
- 优点：最快关闭 G1，供应商支持和历史修订处理能力强。
- 缺点：成本、授权限制、供应商锁定。
- 采购 Gate：不先签长期合同；先要求输出 2019/2020/2021/2023/2025 五个日期的申万一级成员、至少一只调入/调出股票、公告/版本字段。

### B方案：低成本，推荐

| 数据集 | Primary | Backup / 复核 | PIT质量 |
|---|---|---|---|
| 交易日历 | Tushare `trade_cal` | 交易所日历/聚宽 | 高（实测后） |
| 证券主数据 | Tushare `stock_basic` | 上交所/深交所/北交所及退市名单 | 高（实测后） |
| 股票日线 | Tushare `daily` | 聚宽或合格商业 Backup | 高（冲突测试后） |
| 流通市值 | Tushare `daily_basic` | 理杏仁/聚宽可比字段；字段口径必须一致 | 中高 |
| 行业定义 | 申万官方 | Tushare `index_classify` | 高 |
| 历史成分 | Tushare 候选 + 聚宽/理杏仁日期快照 | 申万官方公告/样本文件 | **先 partial；证据链齐全后可升 strict** |
| 宽基指数 | Tushare/指数官方 | 聚宽或交易所 | 中高 |

- 明确成本：Tushare 5000 积分个人官方价当前为 500 元/年；机构为个人价 10 倍。聚宽/理杏仁当前商业套餐需询价。
- 优点：基础数据成本很低，绝大多数 Phase 1B 表可以推进。
- 缺点：strict PIT 仍需人工/半自动归档和断点核对；聚宽、理杏仁按日期返回不自动等于“当时可知”。
- **本报告推荐此方案**：先花 500 元/年解决基础数据，再用小范围试用/POC 决定 strict PIT 辅助源，不先购买昂贵全套终端。

### C方案：免费/最低成本

| 数据集 | Primary | Backup / 复核 | PIT质量 |
|---|---|---|---|
| 交易日历 | 交易所公开日历/AKShare 上游 | 第二官方页面 | 中 |
| 证券主数据 | 三交易所公开上市/退市资料 | 公告归档 | 中高，但整合成本大 |
| 股票日线 | 交易所/公开行情上游经 AKShare | 另一公开上游 | 中；稳定性和授权需审计 |
| 流通市值 | 公开行情上游 | 无合格同口径 Backup 时标 `backup_unavailable` | 中低 |
| 行业定义 | 申万官方文件 | AKShare 仅作下载器 | 高 |
| 历史成分 | 申万官方历史公告/样本档案自行重建 | 公开整理集仅作对照 | **完成档案审计前为 partial** |
| 宽基指数 | 指数公司/交易所公开数据 | 公开行情上游 | 中 |

- 费用：现金成本最低，工程和人工成本最高。
- 优点：不依赖单一商业供应商。
- 缺点：接口不稳定、授权和频控不确定、历史公告归档可能不全、完成时间不可预测。
- 结论：可用于研发和证据搜集；**不能因为“能返回历史日期”就关闭 G1**。

---

## 五、暂时拿不到 strict PIT 时怎么选

### 建议：选择 B，但只作为“独立验证轨”，不能偷换申万 G1

不建议暂停整个项目，也不建议默认用 partial PIT 继续向 Phase 2。

- **不选 A（暂停整个项目）**：Provider、质量、冻结、PIT查询等工程底座已通过，数据源采购/验证可以独立推进；全盘停工没有必要。
- **选择 B（用 PIT 更可靠的分类做验证）**：可在一个明确独立的 `parameter_profile` 下，使用具有官方历史成分和调整公告的指数/分类，验证数据回放、无未来函数、Freeze 和审计链。它只能证明工程可行，**不能代替“申万一级 strict PIT”这一 G1 条件**。如 V2.2 将申万一级写死为唯一生产 taxonomy，则该验证轨需用户批准，且不改变冻结规则。
- **不默认选 C（partial PIT）**：partial PIT 可以做探索、数据清洗和差异定位，但不能用于对外宣称严格历史盲测，也不能为了进入 Phase 2 降低 Gate。

最稳妥的并行方式是：
1. 保持 Phase 2 禁止进入；
2. 用可靠历史指数做工程回放验证；
3. 同时完成申万 strict PIT 采购/归档 POC；
4. 只有申万证据链通过才关闭 G1。

---

## 六、G1 仍缺什么

1. 运行环境中没有可安全调用的 `TUSHARE_TOKEN`；七个接口均未在本环境真实调用。
2. `mainline.security_master` 尚未用真实数据证明包含当前上市和历史退市全量。
3. 2019年至今 `stock_daily` 全A历史回放尚未完成并给出应有/实际/缺失统计。
4. 2019年至今 `float_market_cap_daily` 尚未完成覆盖率和口径验收。
5. `taxonomy_definitions` 尚未用真实申万版本填充并保存版本证据。
6. `membership_history` 尚未通过 5 个历史日期和一只真实调入/调出股票的 strict PIT 验收。
7. 宽基指数 Primary/Backup 尚未连续多次验证稳定。
8. 真实数据的 Primary/Backup 冲突、真实 fallback、真实 Freeze、真实停牌/新股/退市案例尚未形成完整验收证据。
9. 全部生产行的 `source_used/source_version/fetched_at/available_at/run_manifest` 尚未真实对账。
10. 禁止 fixture 写入生产表的结果尚需最终数据审计确认。

---

## 七、哪些问题只需要 Token，哪些不是

### 只要 Tushare Token 和足够积分即可开始解决

- 交易日历：`trade_cal`
- 当前/退市证券主数据候选：`stock_basic`
- 2019年至今日线：`daily`
- 历史流通市值候选：`daily_basic`
- 申万2014/2021分类定义：`index_classify`
- 申万历史成员候选集：`index_member_all`
- 部分宽基指数日线：`index_daily`

这些仍需真实完整性验证；“能调用”不等于“Gate 通过”。

### 即使有 Tushare Token 也不能自动解决

- `index_member_all` 断档、版本名称被后续修订等历史语义问题。
- 历史成员的原始公告时间、首次可得时间和不可变发布快照。
- 申万 `available_at` 的严格重建。
- `index_daily` 不含申万指数日线这一产品边界。
- 合格 Backup 的独立性与同口径证明。
- 供应商事后修订历史时的可审计差异；必须依靠我方快照、哈希和修订日志。
- 数据使用、持久化和团队/机构场景的授权条款。

---

## 八、推荐数据源组合

**推荐 B方案：Tushare 5000 积分 + 申万官方 + 低成本历史成员第二源。**

1. Tushare 5000 积分作为基础 Primary：
   - `trade_cal`
   - `stock_basic`
   - `daily`
   - `daily_basic`
   - `index_classify`
   - `index_member_all`
   - 非申万宽基的 `index_daily`
2. 申万官方作为 taxonomy、版本、调整公告和样本文件的权威来源。
3. 聚宽 JQData 与理杏仁做日期快照交叉验证：
   - 理杏仁重点验证 2021 版；
   - 聚宽重点验证 2019-2020 和分类切换边界；
   - 两者任何一个若不能提供足够历史/授权，立即标 `backup_unavailable=true`，不拿不合格源凑数。
4. 如果官方公告归档不全或上述第二源不能证明 `available_at`，再启动 Wind/Choice/iFinD 付费 POC；不先购买长期合同。
5. 所有抓取原文/文件按内容哈希留不可变快照；供应商历史变更写修订事件，禁止覆盖。

---

## 九、下一步具体执行

### Step 1：最低成本解锁基础数据（1个决策）

安全配置 `TUSHARE_TOKEN`，建议 5000 积分。密钥只进入 Secret/环境变量；禁止写代码、Git、日志或聊天。

### Step 2：先做小样本 POC，不直接全量回灌

按同一个 `run_id` 拉取：
- 2019-06-28
- 2020-06-30
- 2021-12-31
- 2023-06-30
- 2025-06-30

对每个日期保存 Tushare、聚宽/理杏仁、申万官方证据；比较成员集合差异、分类版本和停牌/退市证券保留情况。

### Step 3：完成一只股票的三段证明

选择至少一只真实发生行业调入/调出的股票，输出：
- 调入前：查询不到
- 调入生效后：查询得到
- 调出后：不再属于
- 同时附调整公告发布时间、文件哈希、版本和原始URL

如果只有前两项或没有公告时间，只能判 partial。

### Step 4：历史断点扫描

对每只证券、每个申万一级关系检测：
- 重叠区间
- 无理由空档
- `effective_to < effective_from`
- 2021版切换前后版本混用
- 退市前关系异常消失
- 供应商之间集合差异超阈值

断点不得自动补齐；写入 `research_tasks` 或数据质量失败项。

### Step 5：通过样本 Gate 后再全量

只有 POC 通过后，才回填 2019年至今：
1. security master
2. trading calendar
3. daily
4. daily basic / float market cap
5. taxonomy
6. membership history
7. benchmark

先写 staging，完成覆盖率、冲突和 Freeze 检查后再进入正式表。

### Step 6：G1 Closure 验收

必须重新给出：
- 总证券/当前上市/退市数量
- 日线与市值应有/实际/缺失/完整率
- 五日期申万成员抽查
- 一只股票调入前/调入后/调出后
- Primary/Backup真实冲突测试
- 真实 fallback 和 Freeze
- 停牌/新股/退市真实案例
- 全链路 provenance 与 run manifest

任一 strict PIT 核心项失败，G1继续为“部分通过”，不得进入 Phase 2。

---

## 十、最终八问

1. **G1还缺什么？**  
   缺真实 Token 调用、六类生产数据全量回放和统计、strict PIT 申万历史成员、真实 Backup/冲突/fallback/Freeze，以及真实停牌/新股/退市案例的证据闭环。

2. **哪些问题只需要Token即可解决？**  
   Tushare 可启动交易日历、证券主数据、日线、每日指标/流通市值、分类定义、成员候选、部分宽基数据的抓取。

3. **哪些问题即使有Tushare Token也解决不了？**  
   历史成员的公告/首次可得时间、不可变版本、已知断档与事后修订风险、申万指数日线缺失、合格独立 Backup 和数据授权。

4. **strict PIT最现实的数据来源是什么？**  
   最可靠是经 POC 验证的 Wind/Choice/iFinD 历史申万成员数据，配合申万官方调整公告/样本文件；低成本路线是 Tushare + 聚宽/理杏仁 + 申万官方归档。

5. **是否需要付费？**  
   要想快速、稳定关闭 G1，建议付费。基础数据最低明确支出为 Tushare 5000 积分个人 500 元/年；strict PIT 是否增加付费取决于官方公告档案和低成本 POC 能否补齐 `available_at`。

6. **最低成本方案是什么？**  
   免费官方资料和 AKShare/公开接口可以做 partial PIT；若要提高成功率，最低实用方案是 Tushare 5000 积分 + 申万官方归档 + 聚宽/理杏仁试用或最低套餐。

7. **推荐的数据源组合是什么？**  
   推荐 B方案：Tushare 负责基础数据，申万官方负责权威版本，聚宽/理杏仁做日期级复核；证据不足时再升级 Wind/Choice/iFinD POC。

8. **下一步怎么执行？**  
   先安全配置 Tushare Token；先跑五日期+一只调入/调出股票的小样本；通过后才全量回填；strict PIT不通过则维持 G1 部分通过并继续禁止 Phase 2。

---

## 十一、证据索引

### 官方资料

- Tushare 权限总表：https://tushare.pro/document/1?doc_id=108
- Tushare 积分与频次/价格：https://tushare.pro/document/1?doc_id=290
- Tushare 平台积分：https://tushare.pro/document/1?doc_id=13
- Tushare `stock_basic`：https://tushare.pro/document/2?doc_id=25
- Tushare `trade_cal`：https://tushare.pro/document/2?doc_id=26
- Tushare `daily`：https://tushare.pro/document/2?doc_id=27
- Tushare `daily_basic`：https://tushare.pro/document/2?doc_id=32
- Tushare `index_classify`：https://tushare.pro/document/2?doc_id=181
- Tushare `index_member_all`：https://tushare.pro/document/2?doc_id=335
- Tushare `index_daily`：https://tushare.pro/document/2?doc_id=95
- 申万指数发布页：https://www.swsresearch.com/institute_sw/allIndex/releasedIndex
- 聚宽数据说明：https://www.joinquant.com/help/api/help
- 理杏仁申万2021指定日期成分 API：https://www.lixinger.com/api/open-api/html-doc/cn/industry/constituents/sw_2021
- Wind Client API：https://www.wind.com.cn/mobile/ClientApi/zh.html

### 公开问题/风险证据

- Tushare `index_member_all` 历史区间断档/分类语义问题：https://github.com/waditu/tushare/issues/1924
- Tushare `index_daily` 部分历史区间缺失：https://github.com/waditu/tushare/issues/1861
- Tushare `index_daily` 更新滞后：https://github.com/waditu/tushare/issues/1818
- AKShare 申万接口说明（用于确认上游，不作为原始来源）：https://github.com/akfamily/akshare/blob/main/docs/data/index/index.md

---

## 十二、阶段状态

- Phase 1 工程底座：通过
- Phase 1B 真实数据 Closure：未完成
- Phase 1C 数据源方案：**已形成可执行推荐**
- G1：**部分通过**
- 是否进入 Phase 2：**否**
- 主要阻塞项：真实 Token 未配置；申万 strict PIT 尚未完成 POC、五日期抽查与调入/调出证明
