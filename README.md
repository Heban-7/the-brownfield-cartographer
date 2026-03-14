the-brownfield-cartographer
============================

A multi-agent codebase intelligence system that ingests a Git repository and
produces:

- A structural **module graph** (Surveyor)
- A **data lineage** graph (Hydrologist)
- Optional LLM-powered **semantic understanding** (Semanticist)
- A living **CODEBASE.md** and **onboarding_brief.md** (Archivist)
- An interactive **Navigator** CLI for queries

This is the implementation for *TRP 1 Week 4: The Brownfield Cartographer*.

## Setup

From the project root:

```bash
uv sync
```

This installs all dependencies and the `cartographer` console entry point into
the uv-managed environment.

Optional: copy the environment template and configure OpenRouter:

```bash
cp .env.example .env
# then edit .env and set:
#   OPENROUTER_API_KEY
#   OPENROUTER_BULK_MODEL
#   OPENROUTER_SYNTH_MODEL
#   OPENROUTER_EXPLAIN_MODEL
```

## Basic Usage

### 1. Choose a target repo

Clone a codebase under `target_repos/`, for example Apache Airflow:

```bash
git clone --depth 1 https://github.com/apache/airflow.git target_repos/airflow
```

### 2. Analyze (structural + lineage)

From the Cartographer root:

```bash
uv run cartographer analyze target_repos/airflow --skip-llm
```

This runs:

- Surveyor → builds the module graph
- Hydrologist → builds the data lineage graph

Artifacts are written to:

- `target_repos/airflow/.cartography/module_graph.json`
- `target_repos/airflow/.cartography/lineage_graph.json`
- `target_repos/airflow/.cartography/combined_graph.json`
- `target_repos/airflow/.cartography/cartography_trace.jsonl`
- `target_repos/airflow/.cartography/CODEBASE.md`

### 3. Enable LLM-powered analysis (optional)

If you configured `.env` with an OpenRouter key and models, you can run the
full pipeline:

```bash
uv run cartographer analyze target_repos/airflow
```

This adds:

- Semanticist → purpose statements, domain clustering, Day-One answers
- Archivist → `onboarding_brief.md` enriched with those answers

Outputs:

- `target_repos/airflow/.cartography/CODEBASE.md`
- `target_repos/airflow/.cartography/onboarding_brief.md`

### 4. Query with the Navigator

Launch the interactive Navigator:

```bash
uv run cartographer query target_repos/airflow
```

Available commands:

- `impl <concept>` — semantic-ish search over module paths + purpose text
- `lineage <dataset> <up|down>` — trace data lineage upstream or downstream
- `blast <node>` — blast radius for a module or dataset
- `explain <module_path>` — print stored purpose and optional LLM explanation

### 5. Incremental updates

To re-run analysis only for files changed since the last run (based on git
history and `.cartography/meta.json` timestamp):

```bash
uv run cartographer analyze target_repos/airflow --incremental
```

If no changed files are detected or metadata is missing, the system falls back
to a full scan.

## Second Target Codebase

To satisfy the requirement of running on 2+ real-world codebases, you can
analyze an additional repo such as `dbt-labs/jaffle_shop`:

```bash
git clone --depth 1 https://github.com/dbt-labs/jaffle_shop.git target_repos/jaffle_shop
uv run cartographer analyze target_repos/jaffle_shop --skip-llm
```

The resulting `.cartography/` directory under that repo will contain the same
set of artifacts as for Airflow.
