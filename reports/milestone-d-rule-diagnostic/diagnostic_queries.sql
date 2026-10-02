-- SQLite in-memory; imported frozen archives, no production database.
WITH per_case AS (
 SELECT case_id, case_type, rule_id,
        SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END)*1.0/COUNT(*) AS rate,
        COUNT(*) AS event_days
 FROM main.rule_evidence
 WHERE in_event=1 AND case_type IN ('positive','negative')
   AND rule_id IN ('C4','A','B','C','D','enhancers')
 GROUP BY case_id,case_type,rule_id
)
SELECT rule_id,case_type,AVG(rate) AS rate,COUNT(*) AS cases,
       SUM(event_days) AS cohort_case_days
FROM per_case GROUP BY rule_id,case_type ORDER BY rule_id,case_type;

WITH sizes(n) AS (VALUES(5),(10),(20)), per_case AS (
 SELECT a.case_id,a.case_type,s.n,
        SUM(CASE WHEN r.passed=1 THEN 1 ELSE 0 END)*1.0/COUNT(*) AS rate
 FROM main.anchors a CROSS JOIN sizes s
 JOIN main.context_C r ON r.object_id=a.object_id
  AND r.session_index<a.session_index AND r.session_index>=a.session_index-s.n
 GROUP BY a.case_id,a.case_type,s.n HAVING COUNT(*)=s.n
)
SELECT n,case_type,AVG(rate) AS rate,COUNT(*) AS cases
FROM per_case GROUP BY n,case_type ORDER BY n,case_type;
