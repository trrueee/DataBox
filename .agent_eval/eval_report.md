# DataBox Agent Text-to-SQL Evaluation Report

*Generated at: 2026-06-04T16:42:10.369675+00:00*

## 📊 Overall Performance Summary

| Metric | Value |
| :--- | :--- |
| **Total Test Cases** | 3 |
| **Passed Cases** | 0 |
| **Failed Cases** | 3 |
| **Pass Rate** | **0.0%** |
| **Average Latency** | 63.62s |
| **Total Duration** | 191.02s |

## 📋 Case-by-Case Breakdown

| Case ID | DB | Difficulty | Status | Score | Latency | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `spider-smoke-1` | `concert_singer` | simple | **🔴 FAIL** | 3/5 | 72.7s | Agent SQL execution failed: (1064, "You have an error in your SQL syntax; check the manual that corr |
| `spider-smoke-2` | `concert_singer` | simple | **🔴 FAIL** | 3/5 | 60.0s | Agent SQL execution failed: (1064, "You have an error in your SQL syntax; check the manual that corr |
| `spider-smoke-4` | `concert_singer` | medium | **🔴 FAIL** | 3/5 | 58.2s | Agent SQL execution failed: (1064, "You have an error in your SQL syntax; check the manual that corr |

## 🔍 Deep Dive Details

### ❌ Case `spider-smoke-1` (simple)

- **Question:** How many singers do we have?
- **DB Name:** `concert_singer`
- **Gold SQL:**
  ```sql
  SELECT count(*) FROM singer
  ```
- **Agent SQL:**
  ```sql
  SELECT COUNT(*) AS singer_count FROM singer ORDER BY ARRAY() LIMIT 100
  ```
- **Agent Answer:** I could not complete the analysis because: 执行 SQL 遇到错误: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1")
- **Steps:** build_schema_context, build_query_plan, generate_sql_candidate, validate_sql, execute_sql, revise_sql, profile_result, suggest_chart, suggest_followups, answer_synthesizer
- **Artifacts:** query_plan, sql, safety, insight, error
- **Result:** Agent SQL execution failed: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1")
- **Error:** `执行 SQL 遇到错误: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1")`
- **Quality Score:** 3/5 (checks: {"completed": false, "sql_generated": true, "execution_match": false, "has_safety": true, "has_answer": true, "has_query_plan": true, "has_table": false, "has_error": true, "flow_complete": true})

<details>
<summary>💬 Agent SSE Event Stream</summary>

```json
[
  {
    "event": "agent.run.started",
    "type": "agent.run.started",
    "step": null,
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "build_schema_context",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "build_schema_context",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": "query_plan"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "generate_sql_candidate",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "generate_sql_candidate",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "validate_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "validate_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "validate_sql",
    "error": null,
    "artifact_type": "sql"
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "validate_sql",
    "error": null,
    "artifact_type": "safety"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "execute_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "execute_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "revise_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "revise_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "profile_result",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "profile_result",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "profile_result",
    "error": null,
    "artifact_type": "insight"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "suggest_chart",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "suggest_chart",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "suggest_followups",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "suggest_followups",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "answer_synthesizer",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "answer_synthesizer",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": null,
    "error": null,
    "artifact_type": "error"
  },
  {
    "event": "agent.answer.completed",
    "type": "agent.answer.completed",
    "step": null,
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.run.failed",
    "type": "agent.run.failed",
    "step": null,
    "error": "执行 SQL 遇到错误: (1064, \"You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1\")",
    "artifact_type": null
  }
]
```
</details>

---

### ❌ Case `spider-smoke-2` (simple)

- **Question:** Show name, country, age for all singers ordered by age from the oldest to the youngest.
- **DB Name:** `concert_singer`
- **Gold SQL:**
  ```sql
  SELECT name ,  country ,  age FROM singer ORDER BY age DESC
  ```
- **Agent SQL:**
  ```sql
  SELECT Name AS name, Country AS country, Age AS age FROM singer ORDER BY ARRAY(STRUCT('Age' AS `column`, 'DESC' AS direction)) LIMIT 100
  ```
- **Agent Answer:** I could not complete the analysis because: 执行 SQL 遇到错误: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '(STRUCT('Age' AS `column`, 'DESC' AS direction)) LIMIT 100' at line 1")
- **Steps:** build_schema_context, build_query_plan, generate_sql_candidate, validate_sql, execute_sql, revise_sql, profile_result, suggest_chart, suggest_followups, answer_synthesizer
- **Artifacts:** query_plan, sql, safety, insight, error
- **Result:** Agent SQL execution failed: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '(STRUCT('Age' AS `column`, 'DESC' AS direction)) LIMIT 100' at line 1")
- **Error:** `执行 SQL 遇到错误: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '(STRUCT('Age' AS `column`, 'DESC' AS direction)) LIMIT 100' at line 1")`
- **Quality Score:** 3/5 (checks: {"completed": false, "sql_generated": true, "execution_match": false, "has_safety": true, "has_answer": true, "has_query_plan": true, "has_table": false, "has_error": true, "flow_complete": true})

<details>
<summary>💬 Agent SSE Event Stream</summary>

```json
[
  {
    "event": "agent.run.started",
    "type": "agent.run.started",
    "step": null,
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "build_schema_context",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "build_schema_context",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": "query_plan"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "generate_sql_candidate",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "generate_sql_candidate",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "validate_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "validate_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "validate_sql",
    "error": null,
    "artifact_type": "sql"
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "validate_sql",
    "error": null,
    "artifact_type": "safety"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "execute_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "execute_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "revise_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "revise_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "profile_result",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "profile_result",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "profile_result",
    "error": null,
    "artifact_type": "insight"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "suggest_chart",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "suggest_chart",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "suggest_followups",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "suggest_followups",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "answer_synthesizer",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "answer_synthesizer",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": null,
    "error": null,
    "artifact_type": "error"
  },
  {
    "event": "agent.answer.completed",
    "type": "agent.answer.completed",
    "step": null,
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.run.failed",
    "type": "agent.run.failed",
    "step": null,
    "error": "执行 SQL 遇到错误: (1064, \"You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '(STRUCT('Age' AS `column`, 'DESC' AS direction)) LIMIT 100' at line 1\")",
    "artifact_type": null
  }
]
```
</details>

---

### ❌ Case `spider-smoke-4` (medium)

- **Question:** List all song names by singers above the average age.
- **DB Name:** `concert_singer`
- **Gold SQL:**
  ```sql
  SELECT song_name FROM singer WHERE age  >  (SELECT avg(age) FROM singer)
  ```
- **Agent SQL:**
  ```sql
  SELECT Song_Name AS song_name FROM singer WHERE Age > '(SELECT AVG(Age) FROM singer)' ORDER BY ARRAY() LIMIT 100
  ```
- **Agent Answer:** I could not complete the analysis because: 执行 SQL 遇到错误: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1")
- **Steps:** build_schema_context, build_query_plan, generate_sql_candidate, validate_sql, execute_sql, revise_sql, profile_result, suggest_chart, suggest_followups, answer_synthesizer
- **Artifacts:** query_plan, sql, safety, insight, error
- **Result:** Agent SQL execution failed: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1")
- **Error:** `执行 SQL 遇到错误: (1064, "You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1")`
- **Quality Score:** 3/5 (checks: {"completed": false, "sql_generated": true, "execution_match": false, "has_safety": true, "has_answer": true, "has_query_plan": true, "has_table": false, "has_error": true, "flow_complete": true})

<details>
<summary>💬 Agent SSE Event Stream</summary>

```json
[
  {
    "event": "agent.run.started",
    "type": "agent.run.started",
    "step": null,
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "build_schema_context",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "build_schema_context",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "build_query_plan",
    "error": null,
    "artifact_type": "query_plan"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "generate_sql_candidate",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "generate_sql_candidate",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "validate_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "validate_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "validate_sql",
    "error": null,
    "artifact_type": "sql"
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "validate_sql",
    "error": null,
    "artifact_type": "safety"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "execute_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "execute_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "revise_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "revise_sql",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "profile_result",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "profile_result",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": "profile_result",
    "error": null,
    "artifact_type": "insight"
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "suggest_chart",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "suggest_chart",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "suggest_followups",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "suggest_followups",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.started",
    "type": "agent.step.started",
    "step": "answer_synthesizer",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.step.completed",
    "type": "agent.step.completed",
    "step": "answer_synthesizer",
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.artifact.created",
    "type": "agent.artifact.created",
    "step": null,
    "error": null,
    "artifact_type": "error"
  },
  {
    "event": "agent.answer.completed",
    "type": "agent.answer.completed",
    "step": null,
    "error": null,
    "artifact_type": null
  },
  {
    "event": "agent.run.failed",
    "type": "agent.run.failed",
    "step": null,
    "error": "执行 SQL 遇到错误: (1064, \"You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near '() LIMIT 100' at line 1\")",
    "artifact_type": null
  }
]
```
</details>

---
