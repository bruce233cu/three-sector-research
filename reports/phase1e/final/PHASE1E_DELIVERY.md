# 《A股主线识别系统 V2.2 — Phase 1E 交付结果》

- 原PARTIAL数量：11
- 转SUCCESS数量：1
- 仍PARTIAL数量：10
- FAIL数量：0
- Supabase schema修改：否

| sample_id | 行业 | 成员/有效 | 窗口覆盖 | MA20 | MA60 | NEW_HIGH60 | critical | Freeze | 最终状态 | 原因 |
|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| 2019-06-28:801080 | 电子 | 12/189 | 6.35% | 6.35% | 6.35% | 6.35% | False | True | PARTIAL | sector_return_coverage=0.0635<0.7000;breadth_coverage<0.7000 |
| 2019-06-28:801790 | 非银金融 | 0/50 | 0.00% | 0.00% | 0.00% | 0.00% | False | True | PARTIAL | sector_return_coverage=0.0000<0.7000;breadth_coverage<0.7000 |
| 2020-06-30:801050 | 有色金属 | 0/118 | 0.00% | 0.00% | 0.00% | 0.00% | False | True | PARTIAL | sector_return_coverage=0.0000<0.7000;breadth_coverage<0.7000 |
| 2020-06-30:801120 | 食品饮料 | 0/38 | 0.00% | NULL | NULL | NULL | False | True | PARTIAL | Phase 1E bounded runner did not produce a result |
| 2020-06-30:801790 | 非银金融 | 40/53 | 73.58% | 73.58% | 73.58% | 73.58% | True | False | SUCCESS | - |
| 2021-12-31:801080 | 电子 | 0/361 | 0.00% | 0.00% | 0.00% | 0.00% | False | True | PARTIAL | sector_return_coverage=0.0000<0.7000;breadth_coverage<0.7000 |
| 2021-12-31:801890 | 机械设备 | 0/472 | 0.00% | NULL | NULL | NULL | False | True | PARTIAL | Phase 1E bounded runner did not produce a result |
| 2023-06-30:801050 | 有色金属 | 0/141 | 0.00% | NULL | NULL | NULL | False | True | PARTIAL | Phase 1E bounded runner did not produce a result |
| 2023-06-30:801890 | 机械设备 | 0/550 | 0.00% | 0.00% | 0.00% | 0.00% | False | True | PARTIAL | sector_return_coverage=0.0000<0.7000;breadth_coverage<0.7000 |
| 2025-06-30:801080 | 电子 | 0/491 | 0.00% | 0.00% | 0.00% | 0.00% | False | True | PARTIAL | sector_return_coverage=0.0000<0.7000;breadth_coverage<0.7000 |
| 2025-06-30:801890 | 机械设备 | 0/600 | 0.00% | 0.00% | 0.00% | 0.00% | False | True | PARTIAL | sector_return_coverage=0.0000<0.7000;breadth_coverage<0.7000 |
