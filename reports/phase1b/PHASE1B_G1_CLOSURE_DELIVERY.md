# 《A股主线识别系统 V2.2 — Phase 1B G1 Closure交付包》

## 一、交付结论

- Phase：Phase 1B 真实数据接入与 G1 Closure
- Gate：G1
- 最终状态：**部分通过**
- 是否建议进入 Phase 2：**否**
- 原因：工程底座、远程CI和审计链已通过，但六张核心真实数据表仍为空，strict PIT、Primary/Backup、真实Fallback/Freeze和真实边界案例尚未通过。

## 二、GitHub交付

- 仓库：https://github.com/bruce233cu/three-sector-research
- 分支：`mainline-phase1-import`
- GitHub main：`938fa5b8e4ed6ea7336617b1067ab2e5a9876743`
- 正式 remote baseline：`35b00e09039817b4a9d94c85903a42fb1c39f561`
- Phase 1：`5f0860d2533f4692178c38d7b1f0c63d20c44b00`
- 审计修正与CI：`81799e0219c6ffc24244cad5c91cf466ae6689ec`
- package lock修复：`d7422b5b0b1bcb0114a64eb799f8a4ec1e11f444`
- 只读CI恢复：`055d3fc138016936614444019949ff9f18a8780f`

审计修正：`e48b6ca863175dd601436b1eef10c2e0c4fa0388` 是本地内容谱系，不是正式远程baseline。真实Git历史未重写，未force push。

## 三、Supabase实际状态

项目：`pdtlzleqsoftuxdnbdey`  
schema：`mainline`，后台私有；17张表启用RLS，anon/authenticated无schema usage。

| 表 | 当前行数 | Phase 1B结论 |
|---|---:|---|
| security_master | 0 | 未完成真实导入 |
| taxonomy_definitions | 0 | 未完成真实导入 |
| membership_history | 0 | strict PIT未完成 |
| stock_daily | 0 | 2019年至今未回放 |
| float_market_cap_daily | 0 | 2019年至今未回放 |
| benchmark_daily | 0 | 未完成 |
| trading_calendar | 18 | 已有少量记录，不足以证明2019年至今 |
| source_snapshots | 1 | 审计底座存在 |
| run_manifests | 1 | 审计底座存在 |
| provider_fetch_runs | 1 | 审计底座存在 |

生产核心表没有写入fixture、静态假数据、当前截面历史回填或未知值0。

## 四、真实Provider验收

| 数据集/Provider | 结果 | 证据或原因 |
|---|---|---|
| Tushare Primary | 未真实验证 | 环境不存在可安全使用的TUSHARE_TOKEN |
| BaoStock Backup候选 | 失败/未接入 | SDK可安装，真实连接返回网络接收错误；未冒充已接入 |
| AKShare交易所现有/退市列表候选 | 待真实稳定性验证 | 已定位接口，尚未完成连续调用和生产写入 |
| AKShare申万历史分类候选 | 待严格PIT语义验证 | 接口有分类变更字段候选，但尚未证明available_at、source snapshot及完整变更闭环 |
| AKShare宽基指数候选 | 未完成 | 间歇JSONDecodeError尚未形成合格Backup和连续稳定性证据 |

## 五、strict PIT验收

- 2019年至今申万一级历史成分可查询：**否**
- effective_from/effective_to字段结构：**有**
- 真实数据：**无**
- available_at/source_version/source_snapshot_id真实链：**未建立**
- 当前成分回填历史：**没有**
- 2019/2020/2021/2023/2025五个抽查：**未完成**
- 调入前/调入后/调出后案例：**未完成**
- 结论：strict PIT Gate未通过。

## 六、真实数据完整性

由于核心表为0，下列统计不能伪报：

- 股票主数据总数：0
- 当前上市股票：0
- 历史退市股票：0
- 股票日线：0；最早/最新日期无
- 流通市值：0；最早/最新日期无
- 申万一级行业：0
- 历史成分：0
- 最近交易日行情应有数/成功数/缺失数/完整率：无法形成真实口径

## 七、真实质量、Fallback、Freeze测试

| 验收项 | 状态 | 说明 |
|---|---|---|
| 真实缺失/重复检测 | 未完成 | 无真实核心数据 |
| 真实停牌案例 | 未完成 | 禁止以fixture代替Closure |
| 真实新股不足20日案例 | 未完成 | 同上 |
| 真实退市股历史保留 | 未完成 | security_master/stock_daily为空 |
| Primary/Backup冲突 | 未完成 | 没有两个合格且同时可用来源 |
| 真实Fallback | 未完成 | mock通过不等于真实Provider通过 |
| 真实Freeze | 未完成 | fixture测试通过不等于真实异常链通过 |
| source_used/source_version/fetched_at/available_at | 结构具备，真实链未闭合 | 生产核心数据为空 |
| run_manifest | 1条 | 只能证明审计表可写，不能证明历史回放 |

## 八、CI与测试

Workflow：`.github/workflows/mainline-phase1-ci.yml`

最终已验证的只读CI Run：
https://github.com/bruce233cu/three-sector-research/actions/runs/36236189747

- Commit：`055d3fc138016936614444019949ff9f18a8780f`
- Python mainline：16 PASS，0 FAIL
- Node：11 PASS，0 FAIL
- production build：PASS
- 总计：27 PASS，0 FAIL
- GITHUB_TOKEN权限：contents read

早期两次CI失败已保留审计记录，根因是导入时损坏的`package-lock.json`，不是业务测试失败。临时自修复完成后已移除写权限。

## 九、安全检查

遗留函数：`public.sync_company_market_cap_from_price()`

- SECURITY DEFINER
- 作为`public.price_snapshots`的AFTER INSERT触发器函数
- anon/authenticated/service_role当前均有EXECUTE
- 未发现业务直接RPC引用
- 本阶段未擅自修改，以避免破坏现有三大赛道功能

建议经回归测试后执行最小修复：

```sql
revoke execute on function public.sync_company_market_cap_from_price()
from public, anon, authenticated;
grant execute on function public.sync_company_market_cap_from_price()
to service_role;
```

需先验证REVOKE不影响触发器执行，再部署。该遗留WARN不是mainline Phase 1引入。

## 十、G1自检

- [ ] 2019年至今基础行情真实回放
- [ ] 真实证券主数据包含历史退市股
- [ ] 历史流通市值真实可用
- [ ] 申万一级taxonomy真实可用
- [ ] 申万一级strict PIT历史成分通过
- [x] 当前成分未回填历史
- [ ] Primary真实验证
- [ ] 合格Backup按数据集真实验证
- [ ] Fallback真实验证
- [ ] 数据质量真实数据验证
- [ ] Freeze真实数据验证
- [ ] 停牌/新股/退市真实案例通过
- [ ] source_used真实链可追溯
- [ ] source_version真实链可追溯
- [ ] fetched_at真实链可追溯
- [ ] available_at真实链可追溯
- [x] run_manifest表与审计记录存在
- [x] 自动测试全部通过
- [x] GitHub CI通过
- [x] 无fixture冒充生产数据

G1：**部分通过**

## 十一、关闭G1所需输入

1. 以Secret形式提供可用`TUSHARE_TOKEN`，或提供满足同等字段、时点、历史退市覆盖的Primary。
2. 为后台任务提供可安全使用的Supabase服务连接（不进入聊天、日志、代码或Git）。
3. 明确可获得严格申万历史变更及发布日期/可得时点的数据源；若仅有partial PIT，必须继续标记partial。
4. 完成全A历史Universe、行情、流通市值、宽基和申万PIT的分批幂等回放。
5. 用真实数据补齐双源冲突、Fallback、Freeze、停牌、新股、退市及五日期PIT证据。

## 十二、阶段边界

没有开发RS、WIN、TURNOVER、Breadth、S1/S2/S3/S4、状态机、市场环境、结构标签或AI解释。Phase 2仍被Gate阻止。
