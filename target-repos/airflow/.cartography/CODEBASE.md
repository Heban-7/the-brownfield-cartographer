# CODEBASE — airflow

_Generated: 2026-03-14T14:31:19.074862+00:00_

## Architecture Overview

The repository `airflow` contains 46585 nodes and 21331 edges in the combined knowledge graph. Node composition: FunctionNode=39347, ModuleNode=7238 Edge composition: IMPORTS=21331

## Critical Path (Top Modules by PageRank)

- `airflow-core/src/airflow/serialization/typing.py` (PageRank=0.0474)
- `providers/edge3/src/airflow/providers/edge3/cli/dataclasses.py` (PageRank=0.0235)
- `airflow-core/src/airflow/utils/json.py` (PageRank=0.0109)
- `airflow-core/src/airflow/utils/deprecation_tools.py` (PageRank=0.0090)
- `airflow-core/src/airflow/migrations/versions/0051_3_0_0_update_task_instance_trigger_timeout_to_utcdatetime.py` (PageRank=0.0077)

## Domain Overview

- **unassigned**: 7238 module(s)

## Data Sources & Sinks

### Sources (entry points)
- `dataset:<dynamic:format>`
- `dataset:<dynamic:load>`
- `dataset:<dynamic:read_csv>`
- `dataset:<dynamic:read_json>`
- `dataset:<dynamic:read_parquet>`
- `dataset:<dynamic:read_sql>`
- `dataset:<dynamic:read_table>`
- `dataset:<dynamic:save>`
- `dataset:<dynamic:saveAsTable>`
- `dataset:<dynamic:sqlalchemy>`
- `dataset:<dynamic:to_csv>`
- `dataset:<dynamic:to_json>`
- `dataset:<dynamic:to_parquet>`
- `dataset:INFORMATION_SCHEMA.TABLES`
- `dataset:SELECT * FROM test_csv ORDER BY name`
- `dataset:SELECT * FROM test_table`
- `dataset:YAMMER_GROUPS_ACTIVITY_DETAIL`
- `dataset:a.b`
- `dataset:airlineStats`
- `dataset:any`
- `dataset:bucket`
- `dataset:customers`
- `dataset:dbo.Customers`
- `dataset:default.my_airflow_table`
- `dataset:employees`
- `dataset:example_blob_teradata_csv`
- `dataset:example_blob_teradata_json`
- `dataset:example_blob_teradata_parquet`
- `dataset:example_s3_teradata_csv`
- `dataset:example_s3_teradata_json`
- `dataset:example_s3_teradata_parquet`
- `dataset:exasol_example`
- `dataset:hive.default.example_table`
- `dataset:hive_metastore.temp.sample_table_3`
- `dataset:kylin_example`
- `dataset:my_schema.my_table`
- `dataset:my_schema.source_data`
- `dataset:my_users_dest`
- `dataset:my_users_src`
- `dataset:pet`
- `dataset:sales`
- `dataset:sys.segments`
- `dataset:team`
- `dataset:temp_table`
- `dataset:test_data`
- `dataset:test_table`
- `dataset:tpch.sf1.customer`

### Sinks (terminal outputs)
- `dataset:<dynamic:format>`
- `dataset:<dynamic:load>`
- `dataset:<dynamic:read_csv>`
- `dataset:<dynamic:read_json>`
- `dataset:<dynamic:read_parquet>`
- `dataset:<dynamic:read_sql>`
- `dataset:<dynamic:read_table>`
- `dataset:<dynamic:save>`
- `dataset:<dynamic:saveAsTable>`
- `dataset:<dynamic:sqlalchemy>`
- `dataset:<dynamic:to_csv>`
- `dataset:<dynamic:to_json>`
- `dataset:<dynamic:to_parquet>`
- `dataset:Items`
- `dataset:Orders`
- `dataset:RANDOM_DATA`
- `dataset:SELECT * FROM test_csv ORDER BY name`
- `dataset:SELECT * FROM test_table`
- `dataset:SSL_Users`
- `dataset:Users`
- `dataset:example_bigquery_query`
- `dataset:replace`
- `dataset:script`
- `dataset:tutorial_taskflow_template`

## Known Debt

### Circular dependencies
- Group 1: airflow-core/src/airflow/serialization/typing.py, airflow-core/src/airflow/utils/json.py, providers/edge3/src/airflow/providers/edge3/cli/dataclasses.py
- Group 2: airflow-core/docs/img/diagram_auth_manager_airflow_architecture.py, airflow-core/src/airflow/__init__.py, airflow-core/src/airflow/api_fastapi/common/types.py, airflow-core/src/airflow/api_fastapi/core_api/base.py, airflow-core/src/airflow/api_fastapi/core_api/datamodels/ui/calendar.py, airflow-core/src/airflow/api_fastapi/execution_api/datamodels/asset.py, airflow-core/src/airflow/assets/evaluation.py, airflow-core/src/airflow/assets/manager.py, airflow-core/src/airflow/callbacks/callback_requests.py, airflow-core/src/airflow/configuration.py, airflow-core/src/airflow/dag_processing/bundles/base.py, airflow-core/src/airflow/dag_processing/bundles/manager.py, airflow-core/src/airflow/exceptions.py, airflow-core/src/airflow/executors/workloads/__init__.py, airflow-core/src/airflow/executors/workloads/base.py, airflow-core/src/airflow/executors/workloads/callback.py, airflow-core/src/airflow/executors/workloads/task.py, airflow-core/src/airflow/executors/workloads/trigger.py, airflow-core/src/airflow/io/__init__.py, airflow-core/src/airflow/listeners/listener.py, airflow-core/src/airflow/logging_config.py, airflow-core/src/airflow/macros/__init__.py, airflow-core/src/airflow/models/__init__.py, airflow-core/src/airflow/models/asset.py, airflow-core/src/airflow/models/backfill.py, airflow-core/src/airflow/models/base.py, airflow-core/src/airflow/models/callback.py, airflow-core/src/airflow/models/connection.py, airflow-core/src/airflow/models/crypto.py, airflow-core/src/airflow/models/dag.py, airflow-core/src/airflow/models/dag_version.py, airflow-core/src/airflow/models/dagbundle.py, airflow-core/src/airflow/models/dagrun.py, airflow-core/src/airflow/models/deadline.py, airflow-core/src/airflow/models/deadline_alert.py, airflow-core/src/airflow/models/expandinput.py, airflow-core/src/airflow/models/hitl.py, airflow-core/src/airflow/models/hitl_history.py, airflow-core/src/airflow/models/log.py, airflow-core/src/airflow/models/taskinstance.py, airflow-core/src/airflow/models/taskinstancehistory.py, airflow-core/src/airflow/models/tasklog.py, airflow-core/src/airflow/models/taskmap.py, airflow-core/src/airflow/models/taskreschedule.py, airflow-core/src/airflow/models/team.py, airflow-core/src/airflow/models/xcom.py, airflow-core/src/airflow/observability/traces/__init__.py, airflow-core/src/airflow/plugins_manager.py, airflow-core/src/airflow/providers_manager.py, airflow-core/src/airflow/secrets/__init__.py, airflow-core/src/airflow/serialization/decoders.py, airflow-core/src/airflow/serialization/definitions/assets.py, airflow-core/src/airflow/serialization/definitions/baseoperator.py, airflow-core/src/airflow/serialization/definitions/dag.py, airflow-core/src/airflow/serialization/definitions/deadline.py, airflow-core/src/airflow/serialization/definitions/operatorlink.py, airflow-core/src/airflow/serialization/definitions/param.py, airflow-core/src/airflow/serialization/definitions/taskgroup.py, airflow-core/src/airflow/serialization/definitions/xcom_arg.py, airflow-core/src/airflow/serialization/encoders.py, airflow-core/src/airflow/serialization/helpers.py, airflow-core/src/airflow/serialization/json_schema.py, airflow-core/src/airflow/serialization/serialized_objects.py, airflow-core/src/airflow/settings.py, airflow-core/src/airflow/ti_deps/dep_context.py, airflow-core/src/airflow/ti_deps/dependencies_deps.py, airflow-core/src/airflow/ti_deps/deps/base_ti_dep.py, airflow-core/src/airflow/ti_deps/deps/dag_ti_slots_available_dep.py, airflow-core/src/airflow/ti_deps/deps/dag_unpaused_dep.py, airflow-core/src/airflow/ti_deps/deps/dagrun_exists_dep.py, airflow-core/src/airflow/ti_deps/deps/exec_date_after_start_date_dep.py, airflow-core/src/airflow/ti_deps/deps/mapped_task_upstream_dep.py, airflow-core/src/airflow/ti_deps/deps/not_in_retry_period_dep.py, airflow-core/src/airflow/ti_deps/deps/not_previously_skipped_dep.py, airflow-core/src/airflow/ti_deps/deps/pool_slots_available_dep.py, airflow-core/src/airflow/ti_deps/deps/prev_dagrun_dep.py, airflow-core/src/airflow/ti_deps/deps/ready_to_reschedule.py, airflow-core/src/airflow/ti_deps/deps/runnable_exec_date_dep.py, airflow-core/src/airflow/ti_deps/deps/task_concurrency_dep.py, airflow-core/src/airflow/ti_deps/deps/task_not_running_dep.py, airflow-core/src/airflow/ti_deps/deps/trigger_rule_dep.py, airflow-core/src/airflow/ti_deps/deps/valid_state_dep.py, airflow-core/src/airflow/timetables/_cron.py, airflow-core/src/airflow/timetables/_delta.py, airflow-core/src/airflow/timetables/base.py, airflow-core/src/airflow/timetables/interval.py, airflow-core/src/airflow/timetables/simple.py, airflow-core/src/airflow/triggers/base.py, airflow-core/src/airflow/utils/__init__.py, airflow-core/src/airflow/utils/code_utils.py, airflow-core/src/airflow/utils/dates.py, airflow-core/src/airflow/utils/db.py, airflow-core/src/airflow/utils/db_manager.py, airflow-core/src/airflow/utils/deprecation_tools.py, airflow-core/src/airflow/utils/helpers.py, airflow-core/src/airflow/utils/log/logging_mixin.py, airflow-core/src/airflow/utils/orm_event_handlers.py, airflow-core/src/airflow/utils/platform.py, airflow-core/src/airflow/utils/retries.py, airflow-core/src/airflow/utils/session.py, airflow-core/src/airflow/utils/sqlalchemy.py, airflow-core/src/airflow/utils/types.py, airflow-core/tests/unit/dags/test_heartbeat_failed_fast.py, providers/common/sql/src/airflow/providers/common/sql/dialects/dialect.py, providers/common/sql/src/airflow/providers/common/sql/hooks/sql.py, providers/common/sql/src/airflow/providers/common/sql/operators/sql.py, providers/common/sql/tests/unit/common/sql/hooks/test_sqlparse.py, providers/databricks/src/airflow/providers/databricks/__init__.py, providers/databricks/src/airflow/providers/databricks/hooks/databricks.py, providers/databricks/src/airflow/providers/databricks/hooks/databricks_base.py, providers/databricks/src/airflow/providers/databricks/hooks/databricks_sql.py, providers/databricks/src/airflow/providers/databricks/operators/databricks_sql.py, providers/databricks/tests/unit/databricks/operators/test_databricks_copy.py, providers/google/src/airflow/providers/google/common/deprecated.py, providers/http/src/airflow/providers/http/__init__.py, providers/openlineage/src/airflow/providers/openlineage/__init__.py, providers/openlineage/src/airflow/providers/openlineage/extractors/__init__.py, providers/openlineage/src/airflow/providers/openlineage/extractors/base.py, providers/openlineage/src/airflow/providers/openlineage/extractors/bash.py, providers/openlineage/src/airflow/providers/openlineage/extractors/manager.py, providers/openlineage/src/airflow/providers/openlineage/extractors/python.py, providers/openlineage/src/airflow/providers/openlineage/utils/utils.py, providers/standard/src/airflow/providers/standard/hooks/subprocess.py, providers/standard/src/airflow/providers/standard/operators/bash.py, scripts/ci/prek/common_prek_utils.py, scripts/ci/prek/generate_airflow_diagrams.py, shared/logging/src/airflow_shared/logging/_noncaching.py, shared/logging/src/airflow_shared/logging/percent_formatter.py, shared/logging/src/airflow_shared/logging/structlog.py, task-sdk/src/airflow/sdk/bases/operator.py, task-sdk/src/airflow/sdk/bases/xcom.py, task-sdk/src/airflow/sdk/configuration.py, task-sdk/src/airflow/sdk/definitions/_internal/abstractoperator.py, task-sdk/src/airflow/sdk/definitions/_internal/contextmanager.py, task-sdk/src/airflow/sdk/definitions/_internal/logging_mixin.py, task-sdk/src/airflow/sdk/definitions/_internal/node.py, task-sdk/src/airflow/sdk/definitions/_internal/setup_teardown.py, task-sdk/src/airflow/sdk/definitions/_internal/templater.py, task-sdk/src/airflow/sdk/definitions/asset/__init__.py, task-sdk/src/airflow/sdk/definitions/callback.py, task-sdk/src/airflow/sdk/definitions/context.py, task-sdk/src/airflow/sdk/definitions/dag.py, task-sdk/src/airflow/sdk/definitions/deadline.py, task-sdk/src/airflow/sdk/definitions/mappedoperator.py, task-sdk/src/airflow/sdk/definitions/operator_resources.py, task-sdk/src/airflow/sdk/definitions/param.py, task-sdk/src/airflow/sdk/definitions/taskgroup.py, task-sdk/src/airflow/sdk/definitions/timetables/_cron.py, task-sdk/src/airflow/sdk/definitions/timetables/_delta.py, task-sdk/src/airflow/sdk/definitions/timetables/assets.py, task-sdk/src/airflow/sdk/definitions/timetables/trigger.py, task-sdk/src/airflow/sdk/definitions/xcom_arg.py, task-sdk/src/airflow/sdk/exceptions.py, task-sdk/src/airflow/sdk/execution_time/comms.py, task-sdk/src/airflow/sdk/execution_time/context.py, task-sdk/src/airflow/sdk/execution_time/lazy_sequence.py, task-sdk/src/airflow/sdk/execution_time/xcom.py, task-sdk/src/airflow/sdk/log.py, task-sdk/src/airflow/sdk/providers_manager_runtime.py
- Group 3: airflow-core/src/airflow/api_fastapi/core_api/security.py, providers/fab/src/airflow/providers/fab/auth_manager/api_fastapi/security.py
- Group 4: providers/apache/flink/src/airflow/providers/apache/flink/operators/flink_kubernetes.py, providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/hooks/kubernetes.py
- Group 5: providers/yandex/src/airflow/providers/yandex/hooks/yandex.py, providers/yandex/tests/system/yandex/example_yandexcloud.py


## High-Velocity Files (last 30 days)

- _Git velocity data unavailable_