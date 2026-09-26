# Phase 1B 安全问题清单

## public.sync_company_market_cap_from_price()

核查日期：2026-09-26

### 事实

- 函数类型：trigger function
- 语言：PL/pgSQL
- 权限：SECURITY DEFINER
- search_path：空
- 触发器：public.price_snapshots 的 AFTER INSERT
- 作用：把新价格快照中的 market_cap 与 trade_date 同步到 public.companies
- anon 可直接 EXECUTE：是
- authenticated 可直接 EXECUTE：是
- service_role 可 EXECUTE：是
- 数据库内其他函数直接引用：0

### 风险判断

该函数依赖 trigger 伪记录 new，业务用途是由 price_snapshots 插入触发，不需要作为公开 RPC 被浏览器角色直接调用。PUBLIC 默认 EXECUTE 使它被 Supabase Advisor 判定为 WARN。虽然直接 RPC 调用大概率会因为缺少 trigger 上下文而失败，但保留公开执行权没有业务收益，且扩大了权限面。

### 最小修复建议（本阶段未执行）

```sql
revoke execute on function public.sync_company_market_cap_from_price() from public, anon, authenticated;
grant execute on function public.sync_company_market_cap_from_price() to service_role;
```

触发器内部执行不依赖浏览器角色对 trigger function 的直接 EXECUTE 权限，预期不会破坏价格快照插入后的同步逻辑。正式执行前仍应在事务中完成：

1. 插入一条可回滚的 price_snapshots 测试数据；
2. 验证 companies.market_cap 正常更新；
3. 验证 anon/authenticated 无法 RPC 调用；
4. 回滚测试数据；
5. 再提交单独安全 migration。

本次仅记录方案，未改变现有三大赛道权限或函数定义。
