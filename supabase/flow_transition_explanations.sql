begin;

update public.companies set accounting_status='excluded_scope', accounting_blocker='海外上市公司，仅用于AI光互联供给端验证；当前系统的Step 4聚焦可执行的A股公司利润核算。'
where name in ('GlobalFoundries','Marvell Technology');

update public.companies set accounting_status='not_ready', accounting_blocker='尚未正式入池；客户身份、ASP、单机价值量和正式供货时间未确认，且约350亿元市值超出当前小市值优先范围。'
where name='金力永磁';

update public.companies set status='正式入池→Step 5继续验证', updated_at=now()
where stock_code='603662.SH';

commit;
