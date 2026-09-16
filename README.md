# Three Sector Research System

三大赛道高赔率研究系统：机器人、商业航天、AI。

## Architecture
- GitHub: source code and version control
- Supabase: canonical research database
- ChatGPT Site/Web: research terminal
- ChatGPT: research, evidence-chain updates and system iteration

## Core workflow
原始线索 → 信号验证 → 产业链传导 → 公司机会池 → 公司研究 → 净利润核算 → 估值/赔率 → 关键假设验证 → 历史复盘

## Database modules
- sectors
- companies
- raw_clues
- signals
- signal_companies
- company_events
- profit_models
- valuation_scenarios
- research_snapshots
- daily_reports
- research_tasks

## Environment variables
Copy `.env.example` to `.env.local` and configure the Supabase project values. Never commit secret/service-role keys.
