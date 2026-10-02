# V2.2.1 Clarification — Mainline State Completion

用户显式批准，2026-10-02；包含后续 RS percentile direction correction。
新增规则版本 `mainline_v2.2.1_state_completion_v1`；profile
`industry_trend_v221_state_completion_v1`；clarification
`V2.2.1-mainline-state-completion-2026-10-02`；availability沿用
`mainline_metric_availability_v2.2.1_deferred_circ_mv`。
原V2.2合同与旧profile保持原文，旧历史结果不覆盖。G1/G2保持关闭。

## 正式执行规则

- RS percentile：0最强、1最弱。S1≤0.20、S2≤0.30保持不变。
- WEAKEN三组至少两组：RS5最近5市场日OLS斜率<0（原x=0…4、至少4有效值）；
  RS10分位连续相邻3个市场日严格升高；四项广度较t-3至少三项严格下降。
  S2连续两日满足，仍遵守确认后minimum dwell=3市场日，才转S3。
- RETIRE三组至少两组：RS10<0且RS20<0；RS10分位>0.50（相等不触发）；
  四项广度至少三项低于自身最近20个有效市场日median。
  S3连续三日满足才转S4；禁止S2直接跳S4。
- RECOVER：S3重新满足S2确认谓词连续两日；不能因WEAKEN=false恢复。
- S4关闭旧生命周期；再次符合候选则从新生命周期S1开始，保存prior/reentry。
- Freeze保持可信state，counter_policy=paused，NULL不计成功或失败。
  缺口≤3市场日且逐日质量、规则连续关系、来源和校验均完整补证，恢复计数resumed；
  否则所有升级/转弱/退潮/恢复计数归零reset_after_unverifiable_gap。
  恢复首日只计数，禁止任何硬状态转移。
- E4自身成交集中度分位：250市场日、至少160有效值、SQL percent_rank；≥0.90为高位。
  不足保持NULL。原“非高位或广度同步改善”仍保留：非高位可通过；高位但可靠同步改善
  证据未验收时保持NULL，不填false。核心/中军/家族等enhancement_evidence_deferred，
  不参与上述S3/S4最低谓词，后续MILESTONE E通过新版本启用。

四项广度：up_ratio、above_ma20、above_ma60、new_high_60。
缺失比较始终是未知，不算下降/不算通过；仅当已知结果足够决定2-of-3或3-of-4时作硬判断。
历史窗口只取目标日及此前市场日期。自身percent_rank窗口与既有G2历史分位一样包含目标日。
median取截至目标日最近20个有效市场日，不借未来观测。

## 真实验收边界

每市场日真实解析membership；按当日taxonomy及层级排名，至少10有效行业。
从窗口起点S0自然演化，不手工植入S2/S3。
板块指标必须关联当天成员checksum、源引用。纯函数重放器拒绝静态目标日membership、
缺失日期/分类/成员证据和不足10的横截面。Synthetic fixture只证明代码能力。
没有真实事件与完整输入，不宣称G3 PASS。

当前修订是初始工程参数，不评价收益、不做历史效果调参；以后只能新增rule_version/profile。
