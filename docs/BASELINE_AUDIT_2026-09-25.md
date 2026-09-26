# Phase 1 施工前基线审计（2026-09-25）

本文件只记录在 A 股主线识别模块开工前已经存在于 Sites 源码工作区、但尚未提交的修改。目的不是把未完成能力包装成已验收功能，而是先安全保存已有成果，防止后续施工覆盖或丢失。

## 已有正式功能的未提交成果

- `app/[module]/page.tsx`：V4.4.2 信息源验收页面，区分登记、自动运行、手工可用、未配置、今日成功和历史严格可用。
- `app/api/research/route.ts`：读取来源缺口、重点观察对象和供应链关系。
- `app/globals.css`：V4.4.2 信息源页面样式。
- `hooks/use-research-data.ts`：接收 V4.4.2 新增接口数据。
- `supabase/functions/v43-daily-pipeline/index.ts`：需求、供应链与负面反证来源采集扩展。
- `supabase/schema_v442_demand_and_entities.sql`：需求源与供应链实体补充。
- `supabase/schema_v442_source_acceptance.sql`：来源真实状态、覆盖率口径、盲区与供应链关系结构。

以上内容属于“三大赛道高赔率研究系统”既有 V4.4.2 工作，不属于 A 股主线识别模块。基线固化后，主线模块不得改写其业务语义。

## 未完成开发，先保存但不视为通过

- `supabase/functions/v4-close-recalc/index.ts`：收盘价抓取和重算前置函数。代码已存在，但本次基线审计没有证明其部署、真实运行和端到端验收完成，因此状态保持“未完成开发/待独立验收”。

## 临时测试与部署产物

- 未发现需要删除的临时测试源码。
- `dist`、`.wrangler`、`.sites-runtime`、`node_modules` 等生成或运行目录不纳入 Git 基线。

## 基线验证

- 命令：`npm test`
- 结果：11 个测试全部通过，0 失败，0 跳过。
- 该结果只证明现有测试集通过，不代表未完成的 `v4-close-recalc` 已通过真实数据验收。

## 后续约定

1. 本基线提交只用于安全保存主线模块开工前的工作区状态。
2. A 股主线识别模块从本基线之后单独施工，代码放在 `src/mainline`、`tests/mainline` 和 `mainline` 数据库 schema。
3. GitHub 仓库 `bruce233cu/three-sector-research` 作为唯一 Source of Truth；Sites 内部仓库只作为部署 remote。
