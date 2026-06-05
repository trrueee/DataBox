# DataBox Agent Text-to-SQL Evaluation Report

*Generated at: 2026-06-05T06:41:13.688432+00:00*

## 📊 Overall Performance Summary

| Metric | Value |
| :--- | :--- |
| **Total Test Cases** | 3 |
| **Passed Cases** | 0 |
| **Failed Cases** | 3 |
| **Pass Rate** | **0.0%** |
| **Average Latency** | 2.29s |
| **Total Duration** | 6.88s |

## 📋 Case-by-Case Breakdown

| Case ID | DB | Difficulty | Status | Score | Latency | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `spider-smoke-2` | `concert_singer` | simple | **🔴 FAIL** | 0/5 | 2.4s | DataBox schema preflight failed: [WinError 10061] 由于目标计算机积极拒绝，无法连接。 |
| `spider-smoke-9` | `pets_1` | hard | **🔴 FAIL** | 0/5 | 2.3s | DataBox schema preflight failed: [WinError 10061] 由于目标计算机积极拒绝，无法连接。 |
| `spider-smoke-10` | `pets_1` | extra hard | **🔴 FAIL** | 0/5 | 2.2s | DataBox schema preflight failed: [WinError 10061] 由于目标计算机积极拒绝，无法连接。 |

## 🔍 Deep Dive Details

### ❌ Case `spider-smoke-2` (simple)

- **Question:** Show name, country, age for all singers ordered by age from the oldest to the youngest.
- **DB Name:** `concert_singer`
- **Gold SQL:**
  ```sql
  SELECT name ,  country ,  age FROM singer ORDER BY age DESC
  ```
- **Agent SQL:** *None generated*
- **Result:** DataBox schema preflight failed: [WinError 10061] 由于目标计算机积极拒绝，无法连接。
- **Quality Score:** 0/5 (checks: {"completed": false, "sql_generated": false, "execution_match": false, "has_safety": false, "has_answer": false, "has_query_plan": false, "has_table": false, "has_error": true, "flow_complete": false})

<details>
<summary>💬 Agent SSE Event Stream</summary>

```json
[]
```
</details>

---

### ❌ Case `spider-smoke-9` (hard)

- **Question:** Find the major and age of students who do not have a cat pet.
- **DB Name:** `pets_1`
- **Gold SQL:**
  ```sql
  SELECT major ,  age FROM student WHERE stuid NOT IN (SELECT T1.stuid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat')
  ```
- **Agent SQL:** *None generated*
- **Result:** DataBox schema preflight failed: [WinError 10061] 由于目标计算机积极拒绝，无法连接。
- **Quality Score:** 0/5 (checks: {"completed": false, "sql_generated": false, "execution_match": false, "has_safety": false, "has_answer": false, "has_query_plan": false, "has_table": false, "has_error": true, "flow_complete": false})

<details>
<summary>💬 Agent SSE Event Stream</summary>

```json
[]
```
</details>

---

### ❌ Case `spider-smoke-10` (extra hard)

- **Question:** Find the first name of students who have both cat and dog pets .
- **DB Name:** `pets_1`
- **Gold SQL:**
  ```sql
  SELECT T1.Fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'cat' INTERSECT SELECT T1.Fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid  =  T2.stuid JOIN pets AS T3 ON T3.petid  =  T2.petid WHERE T3.pettype  =  'dog'
  ```
- **Agent SQL:** *None generated*
- **Result:** DataBox schema preflight failed: [WinError 10061] 由于目标计算机积极拒绝，无法连接。
- **Quality Score:** 0/5 (checks: {"completed": false, "sql_generated": false, "execution_match": false, "has_safety": false, "has_answer": false, "has_query_plan": false, "has_table": false, "has_error": true, "flow_complete": false})

<details>
<summary>💬 Agent SSE Event Stream</summary>

```json
[]
```
</details>

---
