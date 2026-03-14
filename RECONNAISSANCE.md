## Target

- **Repo**: `apache/airflow` (shallow clone)
- **Local path**: `target_repos/airflow`
- **Primary focus**: `airflow-core/src/airflow/example_dags/`
- **Date**: (treat as current engagement start)

---

## Five FDE Day-One Questions (Manual Perspective)

### 1. What is the primary data ingestion path?

From exploring the example DAGs and core packages, the main “ingestion path” in this repo is not a single pipeline but a _pattern_:

- DAGs in `airflow-core/src/airflow/example_dags/` read from:
  - External databases via operators like SQL/DB operators (e.g., Postgres, MySQL, Snowflake, BigQuery).
  - File systems / object stores via sensors and file-based operators (S3/GCS/file sensors).
  - APIs and services via HTTP/REST operators and custom Python callables.
- In practice, ingestion is done by:
  - **Operators** that pull data from external systems into intermediate storage (databases, object stores, staging tables).
  - **Sensors** that wait for external data availability.
- The “primary path” is therefore: **external system → operator task → target table/file** within an Airflow DAG, with ingestion defined per-DAG rather than centrally.

**Evidence (files skimmed):**

- `airflow-core/src/airflow/example_dags/` — multiple example DAGs demonstrating:
  - Database reads/writes using SQL operators.
  - File-based processing and transfer tasks.
  - API calls in `PythonOperator` tasks.
- `airflow-core/src/airflow/operators/` — confirms that ingestion is mediated through many operator types.

---

### 2. What are the 3–5 most critical output datasets/endpoints?

Because this is the Airflow _framework_ repository, most example DAGs are illustrative rather than business-critical. The “outputs” that matter from a platform perspective are:

1. **Task and DAG state in the Airflow metadata database**
   - Tables tracking DAG runs, task instances, logs, and scheduling metadata.
   - Everything in the UI and scheduler depends on this state being correct.

2. **Example DAG outputs (demo datasets / files)**
   - Temporary tables created by SQL example DAGs.
   - Example files produced by file-based DAGs.
   - These are important as _documentation_ and test artifacts, not production metrics.

3. **Logs and monitoring signals**
   - Task logs written to local disk / remote storage.
   - Metrics emitted to monitoring systems (statsd, etc.) from core jobs.

From an FDE-onboarding angle, for this repo I would consider the **metadata DB tables and DAG/task state** as the “critical outputs”, because they are the backbone of the platform.

**Evidence (files skimmed):**

- `airflow-core/src/airflow/jobs/` — shows how DAG runs and task instances are persisted.
- `airflow-core/src/airflow/example_dags/` — task-level outputs are mostly demo files/tables.

---

### 3. What is the blast radius if the most critical module fails?

If the DAG/task metadata handling or scheduling logic fails, the blast radius is large:

- **No DAGs run or tasks are scheduled**:
  - Schedulers/jobs in `airflow-core/src/airflow/jobs/` and related DAG parsing code are central.
  - Failures here stop all orchestrated pipelines, regardless of domain.
- **UI and observability degrade**:
  - The webserver relies on metadata tables to show DAG status, task history, and logs.
- **Downstream data products silently stop updating**:
  - Any external warehouse tables, dashboards, or ML pipelines run by Airflow will stall.

So the blast radius is **platform-wide**: all pipelines managed by the affected Airflow deployment.

**Evidence (files skimmed):**

- `airflow-core/src/airflow/jobs/` — scheduler, backfill, and other job classes.
- `airflow-core/src/airflow/dag_processing/` — DAG parsing and processing logic.
- Behavior inferred from how Airflow is typically deployed in production data stacks.

---

### 4. Where is the business logic concentrated vs. distributed?

In this repo the “business logic” is not company-specific; instead:

- **Platform logic is concentrated** in:
  - `airflow-core/src/airflow/models/` — DAGs, tasks, connections, datasets.
  - `airflow-core/src/airflow/jobs/` — scheduling, backfills, maintenance jobs.
  - `airflow-core/src/airflow/operators/` and `hooks/` — integrations with external systems.
- **Usage-specific logic is distributed in DAG definitions**:
  - `airflow-core/src/airflow/example_dags/` contains many small, self-contained DAGs.
  - Each DAG expresses a particular pattern (e.g., branching, sensors, SQL ETL, external APIs).

So the pattern is:

- **Concentrated** platform logic in a relatively small set of “core” packages.
- **Distributed** user/DAG-specific logic across many individual DAG Python files.

**Evidence (files skimmed):**

- `airflow-core/src/airflow/example_dags/` — many small DAGs with domain-agnostic tasks.
- `airflow-core/src/airflow/models/`, `operators/`, `hooks/` — reusable platform abstractions.

---

### 5. What has changed most frequently in the last 90 days (git velocity map)?

Running a quick `git log` over the shallow clone suggests that changes cluster around:

- **Core engine packages**:
  - Scheduler/jobs, models, DAG processing — evolving features and bug fixes.
- **Provider/operator code**:
  - Integrations with external systems (cloud providers, databases, etc.) are updated frequently.
- **Tooling and CI / docs**:
  - GitHub workflows, constraints, and documentation also see regular updates.

On a real engagement, with a full clone and 90-day window, I would run:

```bash
cd target_repos/airflow
git log --since=\"90 days ago\" --name-only --pretty=format: \\
  | sort \\
  | uniq -c \\
  | sort -nr \\
  | head -40
```

and then map the top-changed paths back to their packages (jobs, models, providers, etc.).

For this exercise, I infer:

- High velocity in **core scheduling / models**, **providers/operators**, and **infrastructure files**.

**Evidence (approach):**

- Command above (or equivalent) on a non-shallow clone.
- Repo structure: the areas that are most likely to change match where integrations and behavior live.

---

## What was hardest manually?

- **Navigation blindness**:
  - It’s easy to get lost in thousands of files. Finding “the important few” (scheduler, models, key operators) takes time.
  - Example DAGs are numerous and spread across directories; it’s not obvious which ones best represent real production patterns.

- **Mixed responsibilities**:
  - Core platform logic, provider integrations, and sample usage live in the same repo.
  - Distinguishing “framework behavior” from “example-only behavior” requires reading context in each DAG.

- **Change velocity & ownership**:
  - Without tooling, mapping `git log` output back to conceptual subsystems (e.g., “scheduler vs. providers vs. docs”) is manual and error-prone.
  - It’s not obvious which teams own which areas from the code alone.

- **Cross-cutting concerns**:
  - Data lineage is implicit: tasks call operators which hit external systems; there is no single, explicit data graph.
  - Understanding how a particular dataset is produced/consumed requires manually following operators, hooks, and SQL strings across many files.

These pain points directly motivate the Cartographer design: build structural and lineage graphs, semantic purpose statements, and a Day-One brief so the next engineer doesn’t have to rediscover all of this by hand.
