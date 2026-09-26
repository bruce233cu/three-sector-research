# A股主线识别系统 V2.2 — Phase 1B G1 Closure 状态

日期：2026-09-26  
结论：G1 仍为部分通过；禁止进入 Phase 2。

## 本次已完成

- 核清并修正 remote baseline 审计口径：正式 remote baseline 为 `35b00e09039817b4a9d94c85903a42fb1c39f561`；`e48b6ca...` 仅为本地内容谱系记录。
- 新增并实际运行 GitHub Actions：Python mainline tests、Node tests、production build。
- 修复导入时损坏的 `package-lock.json`。根因是旧导入链把工具的“输出被截断”提示作为文件正文提交。
- 临时自修复工作流完成后，CI 权限已恢复为 `contents: read`，不保留自动写仓库权限。
- 最终只读 CI Run [36236189747](https://github.com/bruce233cu/three-sector-research/actions/runs/36236189747) 成功：Python 16/16，Node 11/11，production build 成功。
- 再次确认执行环境没有可用的 `TUSHARE_TOKEN`、`SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`。
- 核查 SECURITY DEFINER 遗留 WARN，并形成不破坏现有触发器的最小修复建议。
- 评估 BaoStock 作为历史行情 Backup：SDK 可安装，但当前执行环境连接数据服务器失败（网络接收错误）；未登记为已验证。
- 识别 AKShare 的交易所股票/退市列表和申万历史分类候选接口；完成稳定性、字段日期语义和历史完整性验证前，不写入生产表。

## GitHub

- 分支：`mainline-phase1-import`
- Phase 1 commit：`5f0860d2533f4692178c38d7b1f0c63d20c44b00`
- 审计/CI提交：`81799e0219c6ffc24244cad5c91cf466ae6689ec`
- 锁文件修复提交：`d7422b5b0b1bcb0114a64eb799f8a4ec1e11f444`
- 最终只读CI提交：`055d3fc138016936614444019949ff9f18a8780f`
- CI：成功

## 真实数据状态

| 表 | 行数 |
|---|---:|
| mainline.security_master | 0 |
| mainline.taxonomy_definitions | 0 |
| mainline.membership_history | 0 |
| mainline.stock_daily | 0 |
| mainline.float_market_cap_daily | 0 |
| mainline.benchmark_daily | 0 |
| mainline.trading_calendar | 18 |
| mainline.source_snapshots | 1 |
| mainline.run_manifests | 1 |
| mainline.provider_fetch_runs | 1 |

没有用 fixture、当前截面或 0 值补写核心生产数据。

## G1核心阻塞

1. Tushare Primary 无 Token，未真实验证。
2. 2019年至今全A证券主数据、历史行情和流通市值未回放。
3. 申万一级 strict PIT 成分未取得，无法完成 2019/2020/2021/2023/2025 五个历史日期及调入/调出案例。
4. 合格 Backup 未完成稳定性、字段语义、时点口径验收。
5. 真实停牌、新股、退市、双源冲突、Fallback和Freeze尚未全链路完成。

Phase 2 的 RS、WIN、TURNOVER、Breadth、S1-S4、状态机、市场环境、标签及AI解释均未开发。
