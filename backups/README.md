# 站点源码备份

站点：三大赛道高赔率研究系统  
线上地址：https://sanda-saidao-research.zdrzdrzdr233cu.chatgpt.site  
数据库：Supabase `three-sector-research`

## 最新备份

- 备份日期：2026-09-21
- Sites 版本：v36
- Sites 源码提交：`04c434f9d63732b6bf033937985aabbb69dd5d5e`
- Sites 归档内容哈希：`sha256:e2057cf6c7a63a4fddcb4efe30cc65c2e8beef4fb5afa0a83825395ac8a4d5b5`
- GitHub 备份文件：`backups/three-sector-sites-v36-2026-09-21.tar.gz`
- 备份文件 SHA-256：`759c5eb80c5eb34014554328477f94a92e793397cf0507c509561d87c8077719`
- 压缩包大小：304,711 字节
- 源码文件数：143
- 内容：完整可恢复源码，包含应用、数据库迁移、边缘函数、测试、锁文件及 Sites 配置
- 已排除：`.git`、`node_modules`、`.next`、`dist`、`coverage`、`.turbo`、运行缓存和所有 `.env*`
- 安全检查：未发现被写死的运行时密钥、访问令牌、数据库密钥或私钥

恢复：
```bash
tar -xzf backups/three-sector-sites-v36-2026-09-21.tar.gz
npm ci
npm run build
```

部署前须在目标环境重新配置运行时变量；不得把服务端密钥写入仓库。

## 历史备份

- 2026-09-18：日报看板与筛选功能备份
- 2026-09-18：结构化研究表格流程备份
- 2026-09-17：历史日报整合版备份
- 2026-09-17：数据库连接版初始备份
