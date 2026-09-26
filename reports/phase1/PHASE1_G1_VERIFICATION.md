# A股主线识别系统 V2.2 — Phase 1 / G1 验证记录

验证日期：2026-09-26  
最终判定：**部分通过**  
是否进入 Phase 2：**否**

## 可核查结论

- GitHub 共同祖先：`938fa5b8e4ed6ea7336617b1067ab2e5a9876743`（GitHub `main`）。
- Sites 来源审计 SHA：`67b8f9563da3449c6d1c1d123895e5a5cb2d108e`，未迁移该仓库历史。
- GitHub 谱系 baseline：`e48b6ca863175dd601436b1eef10c2e0c4fa0388`。
- Supabase 项目：`pdtlzleqsoftuxdnbdey`；`mainline` 私有 schema 已创建。
- 17 张 `mainline` 表全部启用 RLS；`anon`、`authenticated` 无 schema usage；`service_role` 有 usage。
- 已真实写入：AKShare 1.18.97 交易日历 18 行（2026-09-01 至 2026-09-24）、1 条 source snapshot、1 条 run manifest、1 条 provider fetch audit。
- 未写入静态业务假数据；`security_master`、`taxonomy_definitions`、`membership_history`、`stock_daily`、`float_market_cap_daily`、`benchmark_daily` 均为 0 行。
- Python Phase 1：16/16 PASS；现有 Sites：11/11 PASS；构建成功。

## Provider 实测

| 数据集 | Primary | Backup | 实测结论 |
|---|---|---|---|
| 交易日历 | Tushare `trade_cal` | AKShare `tool_trade_date_hist_sina` | Primary 无 Token 未验证；Backup 成功并落库 |
| 证券主数据 | Tushare `stock_basic` | 无合格 Backup | 均未形成可验收数据 |
| 股票日线 | Tushare `daily` | AKShare 逐标的接口 | Primary 未验证；Backup 批量能力未验证 |
| 流通市值 | Tushare `daily_basic` | 无合格 Backup | 未验证 |
| 申万一级分类 | Tushare `index_classify` | 无合格 Backup | 未验证 |
| 历史行业成分 | Tushare `index_member_all` | 无合格 strict PIT Backup | 仅实现 partial 能力，严格 PIT 未通过 |
| 宽基指数 | Tushare `index_daily` | AKShare `stock_zh_index_daily_em` | Backup 首次返回4行，复测间歇 JSON 失败，标记 degraded |

## PIT 判定

`mainline.membership_history` 已有 `effective_from`、`effective_to`、`available_at`、`source_version`、source snapshot 与防未来数据查询合同。当前真实行数为 0，因此：

- 2019 年至今申万一级行业历史成分：未完成。
- 三个真实历史查询案例：无法提供。
- 调入前/调入后案例：无法证明。
- 当前成分回填历史：没有发生，且代码明确拒绝把 AKShare 当前截面作为 strict PIT。
- 退市股历史保留：schema 与 repository 已实现，尚无真实全量主数据可统计。

## Freeze / Fallback

- Fallback 模拟：Primary 连续失败，调用序列为初始调用 + 2/5/15 秒三次重试，随后 Backup 接管；`source_used=backup`；PASS。
- Freeze 模拟：日线期望 100、实际 94、完整率 94%；输出 `critical_data_ok=false`、`stage_frozen=true`、原因 `daily_bars:completeness=0.9400<0.9500`；PASS。
- 行业成员阈值：91% 仅 warning，89% freeze；符合 V2.2 的 95%/90% 双阈值；PASS。

## 未通过项

1. 缺少 `TUSHARE_TOKEN`，Primary 未真实验证。
2. 2019 年至今全 A 日线、流通市值和证券主数据尚未回放。
3. 2019 年至今申万一级 strict PIT 成分尚未取得，无法完成历史案例验收。
4. 股票日线、流通市值、申万分类/成分无合格且已实测的 Backup。
5. 宽基指数 Backup 存在间歇失败，不能判定稳定可用。
6. 暂未执行真实停牌、新上市、退市、Primary/Backup 冲突全链路数据测试；已有规则与局部单测不等于真实数据验收。

以上任何一项均未被隐藏或以 0、当前截面、静态 fixture 冒充完成结果。
