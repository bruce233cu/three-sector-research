"""Build one readable final-close delivery package from verified evidence."""
from pathlib import Path
import json,zipfile,hashlib

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'reports/milestone-a-final-close'
def fmt(x,percent=False):
    if x is None:return 'NULL'
    return f'{x*100:.2f}%' if percent else str(x)

def main():
    g=json.loads((P/'gate.json').read_text());s=json.loads((P/'snapshots.json').read_text())
    c=json.loads((P/'checks.json').read_text());db=json.loads((P/'database_gate.json').read_text())
    meta=json.loads((P/'delivery_meta.json').read_text())
    rows=['| 日期 | 行业代码 | 有效/成员 | OHLCV/amount | MA20 | MA60 | NEW_HIGH60 | benchmark | 状态 | Freeze |',
          '|---|---|---:|---:|---:|---:|---:|---:|---|---|']
    details=['| 日期 / 行业 | sector_return | benchmark_return | RS5 / RS10 / RS20 | turnover_share / intensity | UP_RATIO | MA20 / MA60 / HIGH60 | Top3成交 |',
             '|---|---:|---:|---|---|---:|---|---:|']
    export=[]
    for x,ch in zip(s,c):
        v=x['metric_coverage_json'];label=x['as_of_date']+' / '+x['taxonomy_code']
        rows.append('| '+ ' | '.join([x['as_of_date'],x['taxonomy_code'],f"{x['valid_member_count']}/{x['member_count']}",fmt(v['OHLCV'],True),fmt(v['MA20'],True),fmt(v['MA60'],True),fmt(v['NEW_HIGH60'],True),fmt(v.get('benchmark'),True),ch['status'],'是' if x['stage_frozen'] else '否'])+' |')
        details.append('| '+' | '.join([label,fmt(x['sector_return'],True),fmt(x['benchmark_return'],True),
             ' / '.join(fmt(x[k],True) for k in ['rs_5','rs_10','rs_20']),
             fmt(x['turnover_share'],True)+' / '+fmt(x['turnover_intensity']),fmt(x['up_ratio'],True),
             ' / '.join(fmt(x[k],True) for k in ['above_ma20','above_ma60','new_high_60']),fmt(x['top3_turnover_share'],True)])+' |')
        export.append({**x,'trade_date':x['as_of_date'],'parameter_profile':x['profile_id'],
                       'metric_availability_version':x['decision_reason']['metric_availability_version'],
                       'status':ch['status'],'OHLCV_coverage':v['OHLCV'],'amount_coverage':v['amount'],
                       'MA20_coverage':v['MA20'],'MA60_coverage':v['MA60'],'NEW_HIGH60_coverage':v['NEW_HIGH60'],
                       'benchmark_coverage':v.get('benchmark')})
    (P/'snapshot_export.json').write_text(json.dumps(export,ensure_ascii=False,indent=2)+'\n')
    blockers=meta['blocking_issues'];text=f'''# A股主线识别系统 V2.2.1
## MILESTONE A FINAL CLOSE / G1 FINAL 交付包

**G1 = {db['G1']}**  
**READY_FOR_PRODUCTION_ENABLEMENT = {str(db['READY_FOR_PRODUCTION_ENABLEMENT']).lower()}**  
MILESTONE A：{'CLOSED' if db['G1']=='PASS' else '未关闭'}。未进入 Phase 2。

本次是断点续跑。真实输入重算：SUCCESS {g['counts']['SUCCESS']} / PARTIAL {g['counts']['PARTIAL']} / FAIL {g['counts']['FAIL']}。
不再把上一轮15条纯缺失输入冻结结果当作真实行情POC。

### 1. benchmark 定义与实现

目标日真实历史 A 股 Universe U_t：当时已上市，且未越过退市日；后来退市股保留
历史资格，未来上市股票不倒灌；B/H股、基金、债券等非A股不进入。
ST不因标签而排除。有效当日个股收益集合 V_t 不包含缺失/无有效交易观测。

benchmark_coverage = |V_t| / |U_t|。只有历史分母已验证且覆盖率≥95%，才输出
benchmark_return = sum(return_i for i in V_t) / |V_t|；不足则 NULL / Freeze。
未知分母的coverage也是NULL，不伪报0%。RS窗口90%与板块内部70%保持不变。

实现：src/mainline/metrics/benchmark.py + scripts/mainline/v221_real_close.py。
新版链路不使用801003；所有RS及60日成交窗口按真实市场日历限定，不能以“最近有效
观测”向前拉长。代码测试通过，但真实benchmark验收不能用代码测试代替。

### 2. 801003与冻结benchmark的差异

801003为申万Ａ指，是申万发布的指数点位序列，其日收益来自点位变化，不是本项目
基于历史有效个股直接计算的等权平均。历史公开申万股价系列编制说明采用流通股本
权重及连锁计算。801003当前完整方法版本、成分范围和调整细则尚未形成项目证据，
因此不声称已复现其全部当前定义，更不能宣称与ALL_A_EQUAL_WEIGHT等价。
两者可能方向相近或某日数值偶合，但这不是等价证明。

受影响：benchmark_return、RS5/10/20、RS派生比较；旧801003成交额代理还会影响
turnover_share/turnover_intensity。旧801003数据保留，只移出新版输入。

核查来源：[申万官方指数发布页](https://www.swsresearch.com/institute_sw/allIndex/releasedIndex)；
[历史申万股价系列编制说明原文](https://finance.sina.com.cn/roll/20031017/0612478149.shtml)。
后者为2003年历史方法，不能冒充801003最新完整编制附件。

### 3. 15样本总表与coverage

OHLCV与amount当日coverage在本次结果中相同，按历史样本成员数计算。
NULL benchmark coverage表示历史全A分母未被证明，不表示观测收益为零。

{chr(10).join(rows)}

### 4. 核心指标总表

{chr(10).join(details)}

每条完整字段、deferred原因、source引用、run/version/profile及Freeze原因见
snapshot_export.json。turnover_cap_deviation与top3_return_contribution全部NULL，
原因明确为deferred_due_to_unproven_historical_circ_mv。

### 5. 来源链、PIT与重跑

原15样本：完整非空旧链5/15，恢复涉及6样本；4条真实登记、9个引用已在前轮恢复，
本次未重新恢复旧source。新版真实来源数、悬空引用及完整链数量见database_gate.json。
本次写后验证：新增35条真实source；成员/行情/日历链15/15；四类完整链0/15，
缺口均为真实benchmark来源；悬空引用0，未登记引用0。没有把组件名单冒充benchmark。
没有为缺失benchmark创建占位来源。Sina真实窗口与成员/日历来源能关联到mainline
source_registry、source_snapshots和run_manifests；缺失的benchmark链如实保留缺口。

本次成功Sina证券 {g['successful_sina_securities']}/{g['requested_sina_securities']}；
临时行情行数 {g['stock_window_rows']}。同输入复算一致 {sum(x['repeat_identical'] for x in c)}/15；
比较核心指标、coverage、Freeze、benchmark、同一source引用及parameter hash。
已有真实行情缓存只复用数据，不伪称再次网络获取，保留原fetched_at和响应checksum。
membership有效日期检查 {g['effective_membership_pit']}/15；全Universe和全部输入PIT
不能据此宣称通过。knowledge_time_unverified=true；Level 2缺失不单独阻塞POC。

### 6. Freeze与NULL验收

代码验证：95%边界可用、94%不足、未来上市/非A/退市日期过滤、非有限收益/重复行情拒绝、
精确20日RS窗口缺失不拉长、重复membership在计算前拒绝、NULL保持NULL、
coverage下降触发Freeze，以及circ_mv deferred本身不触发Freeze。
正式结果的每条Freeze原因、真实coverage和完整对照记录见snapshots.json/checks.json。
原冻结日线质量门槛仍保留；未以板块70%取代其95%关键数据门槛。

### 7. source / manifest / checksum

真实计算代码SHA：{g['code_commit']}  
run_id：{g['run_id']}  
recompute_run_id：{g['recompute_run_id']}  
parameter hash：{g['parameter_hash']}  
workflow：{meta['workflow_run_id']}；artifact：{meta['artifact_id']}  
artifact SHA256：{meta['artifact_sha256']}

最低来源元数据：provider、真实upstream、请求参数及日期、fetched_at、
原始响应checksum（可得时）、标准化checksum、行数、coverage、code SHA、parameter hash、run ID。
证据等级明确。source_snapshots.json保存本轮登记；sina_fetch_audit.json保存逐证券
请求结果；universe_acquisition.json保存真实官方名单请求结果。
原始HTTP响应非永久全量保存不作为自动FAIL理由。

### 8. GitHub与Supabase

仓库：bruce233cu/three-sector-research；分支：mainline-phase1e。
用户给出的52da934是旧检查点；实际起始SHA：25d27a0ff903eee49402832ece6fdad3e121fc89。
本轮提交和最终SHA见delivery_meta.json及GitHub最终提交。报告本身位于交付commit，
避免在报告中伪造自引用commit SHA。

Supabase新增：独立同口径V2.2.1审计profile、15条正式结果、新真实source登记、
原始运行与复算manifest。旧V2.2 15条、前轮冻结15条均不覆盖。证券行情仅临时输入，
不回填全A长期stock_daily库。没有核心schema迁移，没有修改main、Sites、Daily Pipeline、
三大赛道或Phase 2。查询验证与最终数据Gate见database_gate.json/final_gate.sql。

### 9. 最终G1与真正阻塞项

{chr(10).join(str(i+1)+'. '+b for i,b in enumerate(blockers))}

G1={db['G1']}；READY_FOR_PRODUCTION_ENABLEMENT={str(db['READY_FOR_PRODUCTION_ENABLEMENT']).lower()}。
真实benchmark、RS、turnover或PIT缺口未通过时，不能因15条行数齐全而关闭MILESTONE A。

| 冻结验收项目 | 最终结果 |
|---|---|
| 历史taxonomy / membership回放 | 15/15有效日期与SW版本已核对 |
| 无未来membership倒灌 | 15/15成员有效日期检查通过 |
| 真实交易日历 | 3044行，既有来源；未重建 |
| OHLCV / amount | 15/15当日coverage≥96% |
| MA20 / MA60 / NEW_HIGH60市场窗口 | 真实交易日窗口；逐指标coverage见表 |
| ALL_A_EQUAL_WEIGHT | 计算代码已实现；真实历史分母未通过 |
| RS / turnover | NULL，真实端到端可用性未通过 |
| breadth | 15/15真实计算 |
| coverage / NULL / Freeze | 真实覆盖率与NULL保留；15/15冻结；边界测试通过 |
| source / manifest / checksum | 成员行情日历完整；benchmark缺口未通过 |
| effective PIT | 成员有效日期15/15；全A Universe未通过 |
| deterministic rerun | 同输入15/15一致 |
| 正式V2.2.1 snapshot | 已追加15条；0 SUCCESS / 15 PARTIAL / 0 FAIL |
| circ_mv deferred | 两项指标NULL；不构成本轮阻塞 |

### 10. Technical debt（不追加为新Phase 1研究）

Sina当前收益为未复权相邻真实观测close比率；公司行动口径保存warning，未冒充
严格knowledge PIT或未来复权。临时workflow输入artifact保留30天；本包包含输入与
核验checksum，避免只留下不可复算的登记。801003最新完整方法附件未用于本次计算。
不重新研究circ_mv、Tushare、BJ/停牌/退市专项，不以这些名义新增阶段。

### 11. MILESTONE B开工清单（仅PASS后可开工）

metrics finalization；rules；S0-S4；state machine；consecutive days；debounce；
lifecycle；freeze propagation；unit tests；deterministic rerun。
本轮未开工。FAIL时该清单仅为后续范围，不代表Phase 2授权或MILESTONE A关闭。

### 12. 优化留痕与执行规范

为什么改：前轮仅生成缺失输入结果，未满足真实Sina与来源链验收。改了什么：在既有
主链上获取并缓存真实窗口、重算固定15样本；修复官方SH终止上市名单B股混入风险；
记录完整元数据与同输入复算。版本V2.2.1，业务阈值不变，数据库仅mainline追加，
不改状态筛选/生产自动化，不覆盖旧数据。验收结果以本包G1为准；未解决问题仅限上列。

使用[Supabase技能](skill://supabase@openai-curated-remote/root/.codex/plugins/cache/openai-curated-remote/supabase/1.0.0/skills/supabase/SKILL.md)
完成mainline限定写入和写后验证；遵循[Postgres批量写入规范](https://www.postgresql.org/docs/current/sql-copy.html)
将15条结果和来源批量纳入事务。用户禁止影响三大赛道优先于共享public优化日志默认规则，
优化记录写入mainline manifest与此报告。
'''
    (P/'DELIVERY.md').write_text(text)
    bundle=ROOT/'A股主线识别系统_V2.2.1_MILESTONE_A_FINAL_CLOSE_交付包.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in P.glob('*'):
            if p.is_file():z.write(p,'交付包/'+p.name)
        for p in ['src/mainline/metrics/benchmark.py','src/mainline/metrics/sector.py','src/mainline/metrics/availability.py','src/mainline/providers/phase1f_free.py','scripts/mainline/v221_real_close.py','scripts/mainline/v221_final_close.py','tests/mainline/test_v221_benchmark.py','docs/V221_FINAL_CLOSE_AUDIT_CONTRACT.md','docs/V2_2_1_BENCHMARK_COVERAGE_CLARIFICATION.md','reports/milestone-a-fast-close/calendar_input.json']:
            z.write(ROOT/p,'交付包/代码/'+p)
    print(bundle);print(hashlib.sha256(bundle.read_bytes()).hexdigest())
if __name__=='__main__':main()
