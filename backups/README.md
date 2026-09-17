# 站点源码备份

- 备份日期：2026-09-17
- 站点：三大赛道高赔率研究系统
- 线上地址：https://sanda-saidao-research.zdrzdrzdr233cu.chatgpt.site
- 数据库：Supabase `three-sector-research`
- 备份内容：完整可恢复源码（不含依赖缓存、构建产物和密钥）
- 恢复方式：解压 `backups/three-sector-source-2026-09-17.tar.gz` 后执行 `npm ci` 与 `npm run build`。

站点运行时通过 `SUPABASE_URL` 和 `SUPABASE_PUBLISHABLE_KEY` 读取公开研究数据；敏感凭据不得写入仓库。
