# Phase 1F-C · 外部 POC 执行包

目的：为 **三个历史板块** 更换临时行情输入，复用既有计算器。不是个股研究系统。

交付状态：执行包离线验证；免费源真实 POC **未开始**，G1 状态不变。

## 开始：三条命令

解压 ZIP，在 `mainline_phase1f_c` 根目录打开终端。推荐 Python **3.12**，Windows / macOS / Linux，约 1GB 可用磁盘。不要在旧工程工作目录直接覆盖解压。

```bash
python -m venv .venv
```

激活：Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`；macOS/Linux 使用 `source .venv/bin/activate`。如果激活被系统策略禁止，直接使用 `.venv` 内的 Python，不修改系统策略。

```bash
python -m pip install -r scripts/mainline/phase1f_c/requirements-poc.txt
python scripts/mainline/phase1f_c/run.py --preflight
python scripts/mainline/phase1f_c/run.py --external-network-approved
```

使用 uv 可替换为 `uv venv --python 3.12`、`uv pip install -r ...`，其余不变。没有自动安装，不在 Work 运行联网命令。顶层依赖锁定；安装后的全部依赖版本写入 environment.json。

首次默认只安装 pytdx。若输出 `BLOCKED_DEPENDENCY` 且原因是缺少 AKShare，**先查 TDX 记录确已不通过**，再安装新浪依赖并重跑完整顺序：

```bash
python -m pip install -r scripts/mainline/phase1f_c/requirements-sina.txt
python scripts/mainline/phase1f_c/run.py --external-network-approved
```

pytdx 1.72 是老版本，原项目已归档；兼容性/授权风险不可视为已验证。安装失败属于环境/依赖阻塞，不是行情源失败。不要装 pytdxdata 或 qstock 来绕过失败。

## 网络要求

| 用途 | 访问目标 | 网络 |
|---|---|---|
| 安装依赖 | pypi.org、files.pythonhosted.org，或用户批准的镜像 | HTTPS 443 |
| 通达信 | 固定 pytdx 包的 hq_hosts 列表，运行时最多测8个节点 | 出站 TCP，常见7709；实际按列表端口 |
| 新浪原始日线 | finance.sina.com.cn | HTTPS 443 |
| 既有申万801003基准/市场成交额输入 | www.swsresearch.com | HTTPS 443 |

只放行 HTTPS 不足以连接通达信。可通过 `--servers-file servers.json` 指定经用户批准的当前节点，例如 JSON 数组，每项为 `name/host/port`；不随包硬编码旧IP。

Sina 真实上游记录为新浪；AKShare 1.18.97 只复用 `stock_zh_a_daily` 所使用的 URL 常量和原始 JS 解码。**不调用该函数的股本合并/ffill路径**，不补齐停牌行，不使用股本字段代替成交额。amount 必须由原始日线返回，缺失则不通过健康检查。复权参数为不复权。

qstock 默认排除：其已核对的历史日K仍调用东方财富。没有 Eastmoney / NetEase / BaoStock 股票行情请求或付费源回退。

申万输入复用既有 `get_sw_index('801003')`，不是新基准或自行拼全A。该旧方法仍 `verify=False`：本包未顺手修改，结果标注传输真实性未验证；正式验收应评估这一风险。源不可达时输出 `BLOCKED_BENCHMARK_INPUT`，不能把股价源判失败。可用 `--benchmark-file` 指定既有可信基准导出（JSON含 source_id=sws_official_index_api、amount_unit=CNY、rows、checksum；checksum为rows的规范JSON SHA256）。不猜测或换基准。

## 健康检查与正式运行

```bash
python scripts/mainline/phase1f_c/run.py --health-check --external-network-approved
```

五只真实历史成员，覆盖三个日期，每只独立请求两次。健康检查通过需：至少80%探测证券得到60根有效历史日线、目标日期存在、OHLC关系和量额单位校验通过、两次窗口校验和一致，且每个目标日期至少一只成功。输出 `HEALTH_PASS_ONLY` 只说明健康，不说明板块通过。

正式命令会重新健康检查，再顺序运行三个样本，两轮均重新请求行情（不以缓存命中冒充源稳定性）；每轮各调用既有计算器两次核验相同输入。Provider不并行。通过一个源后立即停止；不补其他样本。

最多8个服务器测速；每次连接最多2次；每证券一次有界获取、最多16页×800根。行情页中超出目标窗口的记录立即丢弃，不长期保存。单证券20秒进程级截止，样本每轮最多30分钟，同一Provider整个批次两轮最多90分钟。进程阻塞会终止隔离子进程，不卡住其他样本。预算不足记 `INCONCLUSIVE_BUDGET`，不是源能力失败。

预计单源两轮约10～60分钟，**未实测，不能保证**；两候选预算上限合计约3小时另加初始化/健康/基准检查。代码有进度输出，不能等待无上限。慢网络可导致结果未完成，不能制造通过。

## 如何看结果

每次生成独立目录 `artifacts/phase1f_c/<UTC时间>/`，不覆盖上次。

| 文件 | 内容 |
|---|---|
| summary.json | 整体状态、推荐源、重跑差异、circ_mv缺口 |
| samples.csv / metrics_output.json | 3样本×2轮（每个已进入批次的Provider），指标与Freeze |
| provider_health.json | 版本、节点测速、五只证券两次请求、错误及耗时 |
| coverage_report.json | 严格交易日窗口与冻结计算器覆盖率 |
| run_manifest.json / source_manifest.json | run_id、来源版本、成员/代码完整性、证券窗口校验和 |
| checksums.json | 所有结果文件的字节校验和（不含自己/ZIP） |
| errors.json | 单证券失败、缺字段、空结果、超时、未尝试证券 |
| environment.json | OS、Python、全部依赖版本、时区、分支/SHA、执行时间 |
| phase1f_c_results.zip | 可交回Work的标准结果包；不含临时个股行情缓存 |
| cache/ | 仅三个样本各自窗口，临时JSON，默认两轮不复用 |

`MARKET_WINDOW_POC_PASS_CIRC_MV_GAP`：三个样本两轮MA20/MA60/NEW_HIGH60均≥70%，无Freeze、非circ_mv核心指标全部可生成、量额覆盖≥70%、PIT/相同输入计算一致、独立两轮结果/错误统计一致；行情窗口POC通过。**不是完整G1通过**。

`POC_NOT_PASSED_REVIEW_ERRORS`：健康或实测板块条件未满足，需要按错误区分网络环境、缺字段、旧证券、历史不足，不能把所有错误概括为免费源失败。

`BLOCKED_DEPENDENCY` / `BLOCKED_BENCHMARK_INPUT` / `INCONCLUSIVE_BUDGET`：前置条件或预算阻塞，不能判行情Provider失败/通过。

`circ_mv` 全部保持NULL，不读取当前股本或从成交额伪造。现有 `turnover_cap_deviation` 与 `top3_return_contribution` 依赖circ_mv，继续保持NULL；不因此把行情源整体判失败，但不能宣称全指标集已闭环。

精确60市场交易日来自同一申万基准，输入裁剪到目标日及此前60日。停牌/无交易占位不填充，新股不足自然降低覆盖。冻结计算器完全不变；若原计算器按观察行计数导致MA20纳入过旧/间断价格，其覆盖与精确窗口有差异，则单独标记并禁止宣布POC通过，不顺手改公式/Freeze。股票收益沿用不复权相邻有效观察收盘比；除权处理口径仍需正式验收，不暗中切换前复权。

历史成员取自指定 GitHub提交的现有导出，仅抽取189/472/491条；effective日期、样本日期、成员数、PIT标记和代码/配置校验和启动时检查。knowledge_time_unverified始终true，不升级PIT。

## 交回结果与清理

先在外部校验：

```bash
python scripts/mainline/phase1f_c/run.py --verify artifacts/phase1f_c/实际运行目录
```

将 `phase1f_c_results.zip` 上传回此对话。不要上传账号、token、.env、虚拟环境或整个项目。包内无Supabase配置或写入路径；脚本不读取用户环境密钥。

Work收到后验证三样本范围、输入/源/校验和、PIT、单位、复权、NULL、Freeze和重跑差异；hash通过只证明完整性，不证明数据真实，也不自动写回。只有另行确认验收与写入授权，才考虑mainline已有结构。原SUCCESS/其他PARTIAL不得被覆盖。

临时缓存建议复核后7天内清理（无定时任务）：

```bash
python scripts/mainline/phase1f_c/run.py --clean-cache artifacts/phase1f_c/实际运行目录
```

只删除指定、有summary标记的单次run/cache，保留结果文件；删除后无法恢复，需重新获取。严禁递归删除整个项目或使用宽泛路径。不会建立长期stock_daily/float_mv数据库。服务器故障、TLS报错、安装失败、TCP不允许等保留原错误，不关闭安全策略绕过权限。

## 离线测试与包身份

`python -m unittest discover -s tests/mainline -p test_phase1f_c.py -v`：合成测试只验证代码防护，不代表真实Provider通过。

`integrity.json`固定成员、三个样本配置、计算器及运行代码SHA256。 ZIP无.git时，Git SHA记录为已核验基线提交，额外代码身份以该完整性清单为准；仓库运行会记录实际Git HEAD，不能把基线SHA当成本轮代码提交SHA。

本轮不修改Supabase、UI、公式、状态机或其他模块。AGENTS要求的共享优化记录写入与本轮禁止生产写入冲突，因此只在此mainline交付文档留痕，不写共享表。执行包完成后停止，等待用户外部运行结果。
