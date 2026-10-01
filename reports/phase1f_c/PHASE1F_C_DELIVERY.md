# A股主线识别系统 V2.2 — Phase 1F-C 外部POC执行包交付说明

日期：2026-10-01。分支：`mainline-phase1e`。

## 交付结论

完成最小外部执行包。25项合成离线测试通过；解压后的同一测试通过；ZIP完整性验证通过。**没有真实请求通达信或新浪，也没有验证外部pip安装或客户端网络兼容性。**

Phase 1F-B仍为“环境阻塞 / POC未开始”。免费Provider不能判通过或失败，G1仍部分通过；未运行其他PARTIAL或Phase 2。

## 文件

- `scripts/mainline/phase1f_c/requirements-poc.txt`：pandas/numpy/requests/pytdx固定版本。
- `scripts/mainline/phase1f_c/requirements-sina.txt`：可选AKShare 1.18.97。
- `scripts/mainline/phase1f_c/README_PHASE1F_C.md`：安装、网络、命令、状态、结果、清理及回交。
- `scripts/mainline/phase1f_c/config.json`：唯一三样本配置及有界预算。
- `scripts/mainline/phase1f_c/membership.json`：189/472/491条既有历史成员证据，共1152条，不是当前成员。
- `scripts/mainline/phase1f_c/integrity.json`：成员/样本/既有公式/参数/新增脚本校验和。
- `scripts/mainline/phase1f_c/run.py`：外部执行入口、离线preflight/verify。
- `scripts/mainline/phase1f_c/build.py`：离线白名单ZIP打包器。
- `src/mainline/providers/phase1f_free.py`：通达信分页、节点选择；新浪原始解码，无ffill。
- `src/mainline/poc/phase1f_c.py`：有界串行、独立两轮请求、同输入计算重跑、结果清单。
- `tests/mainline/test_phase1f_c.py`：25项离线测试，测试桩拒绝网络调用。
- 本文档。

生成文件：`artifacts/phase1f_c_package/mainline_phase1f_c_external_poc.zip`，只含mainline必要代码、只读参数及测试，不包含三大赛道代码、密钥、缓存或数据库连接器。

## 身份与隔离

基线远端HEAD：`6391737d3398479f70e21d7eb4d8f12dbe1ddb1a`。原计算器、历史成员适配器、基准读取方法、参数及导入依赖已逐文件核对，与该基线Git blob一致。为保持原providers导入契约，ZIP含原类定义，但不会实例化Tushare或调用东财个股方法；申万基准仅复用既有get_sw_index。

本地既有两个Phase 1E未提交修改没有被覆盖或一并提交。本轮只新增上述mainline文件，以远端基线建树，避免把落后的本地分支覆盖到远端。

Supabase只读核对mainline样本和来源。membership_history表当前没有成员行；转而复用远端 `reports/phase1d/runtime/membership_evidence.json` 的可解析历史导出，严格抽取三个样本。完整final-v2文件无法解析，未修复、未猜测、未拿当前成员替代。

AGENTS要求写共享系统优化记录，与用户本轮禁止生产写入冲突；遵循用户边界，只以mainline文档留痕，不写共享表。

## 运行

解压后在根目录，Python3.12虚拟环境中：

```bash
python -m pip install -r scripts/mainline/phase1f_c/requirements-poc.txt
python scripts/mainline/phase1f_c/run.py --preflight
python scripts/mainline/phase1f_c/run.py --external-network-approved
```

通达信无法通过，且结果提示可选AKShare依赖缺失时，查看TDX记录后安装 `requirements-sina.txt`，再运行同一命令，保持TDX→Sina顺序。qstock默认排除。

TCP节点从固定库配置读取，最多测速8个，常见7709；允许运行时覆盖节点清单。新浪finance.sina.com.cn HTTPS443；申万基准www.swsresearch.com HTTPS443；依赖pypi.org/files.pythonhosted.org HTTPS443。

单源预计10～60分钟（未实测），全两轮批次预算90分钟，单证券20秒、单样本每轮30分钟。预算耗尽是未完成，不推断Provider历史能力失败。外部用户可中止；本轮Work不运行这些命令。

## 验收与缺口

健康：五只历史成员各两次，三个日期均有有效探测，80%探测成功，OHLCV/amount/单位/复权和重复窗口通过。仅健康通过不是板块通过。

板块：三个样本两轮窗口覆盖≥70%、现有非circ_mv核心指标可计算、NULL和Freeze正确、有效PIT、同输入计算一致、独立请求重跑结果/错误统计一致且来源可追溯。

`MARKET_WINDOW_POC_PASS_CIRC_MV_GAP`明确只通过行情输入窗口。circ_mv仍NULL，影响turnover_cap_deviation及top3_return_contribution，不谎称全指标集或G1通过。

精确交易日窗口校验只作为POC验收防护，不修改冻结计算器；如原观察行计数与准确窗口覆盖不同，记录差异、不宣布通过。基准不可得、依赖不可用、预算不足分别输出阻塞/未完成状态。

额外已知风险：pytdx老版本及原项目授权限制；旧申万基准方法verify=False，传输真实性未验证；不复权收益在除权日期的口径风险。以上不通过本轮包生成消除，不进入正式生产接入。

## 回交及清理

输出 `artifacts/phase1f_c/<UTC时间>/`，含标准10项JSON/CSV及结果ZIP、临时cache。

上传 `phase1f_c_results.zip` 回Work。结果ZIP不含个股OHLC明细；保留本地临时缓存供短期复核，验收后建议7天内清理。Work重新核验证据，后续写回需要另行确认。

```bash
python scripts/mainline/phase1f_c/run.py --verify artifacts/phase1f_c/实际运行目录
python scripts/mainline/phase1f_c/run.py --clean-cache artifacts/phase1f_c/实际运行目录
```

清理只删除该run的cache，不可恢复，保留报告。没有自动生产写入、自动补数、长期个股库或调度任务。

## 明确回答

修改main：否。新业务分支：否。Supabase schema：否。生产写入：否。非mainline模块：否。UI：否。长期个股数据库：否。Phase 2：否。

代码提交身份以分支最终GitHub提交为准；ZIP内容身份以integrity.json为准。完成本包后停止，等待用户外部结果。
