## Target

- Repo: apache/airflow (shallow clone)
- Focus area: airflow-core/src/airflow/example_dags/
- Date:

## Five FDE Day-One Questions (Manual)

### 1) Primary data ingestion path

- Answer:
- Evidence (files you looked at):

### 2) 3–5 most critical outputs (datasets/endpoints)

- Answer:
- Evidence:

### 3) Blast radius if the most critical module fails

- Answer:
- Evidence:

### 4) Where is business logic concentrated vs distributed?

- Answer:
- Evidence:

### 5) What changed most frequently in last 90 days (velocity map)

Count Name Group

---

    1 providers/google/tests... {providers/google/tests/integration/google/cloud/transfers/test_mssql_to_gcs.py}
    1 providers/google/tests... {providers/google/tests/integration/google/cloud/transfers/test_bigquery_to_mssql.py}
    1 providers/google/tests... {providers/google/tests/integration/google/cloud/transfers/test_trino_to_gcs.py}
    1 providers/google/tests... {providers/google/tests/system/google/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/__init__.py}
    1 providers/google/tests... {providers/google/tests/integration/google/cloud/transfers/__init__.py}
    1 providers/google/tests... {providers/google/tests/deprecations_ignore.yml}
    1 providers/google/tests... {providers/google/tests/conftest.py}
    1 providers/google/tests... {providers/google/tests/integration/__init__.py}
    1 providers/google/tests... {providers/google/tests/integration/google/cloud/__init__.py}
    1 providers/google/tests... {providers/google/tests/integration/google/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/ads/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/bigquery/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/azure/example_azure_fileshare_to_gcs.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/bigquery/example_bigquery_dataset.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/bigquery/example_bigquery_jobs.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/bigquery/example_bigquery_dts.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/azure/example_azure_blob_to_gcs.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/ads/example_ads.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/alloy_db/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/azure/example_azure_blob_to_gcs.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/ads/example_ads.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/alloy_db/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/azure/__init__.py}
    1 providers/google/tests... {providers/google/tests/system/google/cloud/alloy_db/example_alloy_db.py}
    1 providers/google/src/a... {providers/google/src/airflow/providers/google/marketing_platform/sensors/display_video...
    1 providers/google/src/a... {providers/google/src/airflow/providers/google/marketing_platform/sensors/campaign_mana...
    1 providers/google/src/a... {providers/google/src/airflow/providers/google/suite/__init__.py}
    1 providers/google/src/a... {providers/google/src/airflow/providers/google/suite/hooks/calendar.py}
    1 providers/google/src/a... {providers/google/src/airflow/providers/google/suite/hooks/__init__.py}
    1 providers/google/src/a... {providers/google/src/airflow/providers/google/marketing_platform/sensors/bid_manager.py}
    1 providers/google/src/a... {providers/google/src/airflow/providers/google/marketing_platform/operators/campaign_ma...

- Evidence (commands + observations):

## What was hardest manually?

- Navigation blind spots:
- Missing / stale docs:
- Cross-language / config pain:
- Anything surprising:
