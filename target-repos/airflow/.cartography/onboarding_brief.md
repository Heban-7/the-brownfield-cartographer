# Onboarding Brief — airflow

_Generated: 2026-03-14T14:31:19.077126+00:00_

## The Five FDE Day-One Questions

### 1. What is the primary data ingestion path?
- _To be refined via Semanticist/Navigator; initial hints from data sources in `CODEBASE.md`._

### 2. What are the 3–5 most critical output datasets/endpoints?
- _See Data Sinks section in `CODEBASE.md`; sort by business importance once known._

### 3. What is the blast radius if the most critical module fails?
- _Use the `cartographer blast-radius` CLI on candidate modules/datasets._

### 4. Where is the business logic concentrated vs. distributed?
- _Approximate via high PageRank modules and domain clusters (if Semanticist ran)._

### 5. What has changed most frequently in the last 90 days?
- _See High-Velocity Files section in `CODEBASE.md`._

> NOTE: This brief is a scaffold; for a full answer you will typically
> re-run the Semanticist with appropriate API keys and use the Navigator
> agent to cross-check answers against specific files and line ranges.