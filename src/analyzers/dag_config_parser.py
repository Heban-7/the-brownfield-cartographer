"""Airflow DAG and dbt YAML configuration parser.

Extracts pipeline topology from:
- Airflow Python DAG files (DAG() instantiation, operators, >> dependencies)
- dbt schema.yml / dbt_project.yml (model definitions, ref() dependencies, sources)
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from src.models.nodes import (
    DatasetNode,
    StorageType,
    TransformationNode,
    TransformationType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Airflow DAG parsing
# ---------------------------------------------------------------------------


def _is_airflow_dag_file(path: Path) -> bool:
    """Quick heuristic: does the file mention DAG or airflow?"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:5000]
        return "DAG" in text or "airflow" in text.lower()
    except Exception:
        return False


def parse_airflow_dag(path: str | Path) -> dict[str, Any]:
    """Parse an Airflow DAG Python file and extract topology.

    Returns a dict with:
      - dag_id: str
      - tasks: list[dict] with task_id, operator_class, args
      - dependencies: list[(upstream, downstream)]
      - datasets: list[DatasetNode] (SQL tables / file paths referenced)
      - transformations: list[TransformationNode]
    """
    path = Path(path)
    if not path.is_file():
        return {}

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return {}

    result: dict[str, Any] = {
        "dag_id": "",
        "tasks": [],
        "dependencies": [],
        "datasets": [],
        "transformations": [],
        "source_file": str(path),
    }

    result["dag_id"] = _extract_dag_id(source)
    result["tasks"] = _extract_tasks(source, str(path))
    result["dependencies"] = _extract_dependencies(source)

    for task in result["tasks"]:
        datasets, transforms = _task_to_lineage(task, str(path))
        result["datasets"].extend(datasets)
        result["transformations"].extend(transforms)

    return result


def _extract_dag_id(source: str) -> str:
    match = re.search(r"""DAG\s*\(\s*['"]([^'"]+)['"]""", source)
    if match:
        return match.group(1)
    match = re.search(r"""dag_id\s*=\s*['"]([^'"]+)['"]""", source)
    if match:
        return match.group(1)
    return ""


def _extract_tasks(source: str, source_file: str) -> list[dict]:
    """Extract operator instantiations using regex (robust against unparseable files)."""
    tasks: list[dict] = []
    operator_pattern = re.compile(
        r"""(\w+)\s*=\s*(\w*Operator|\w*Sensor|\w*Task)\s*\(""",
        re.MULTILINE,
    )
    for match in operator_pattern.finditer(source):
        var_name = match.group(1)
        operator_class = match.group(2)

        task_id_match = re.search(
            rf"""{re.escape(var_name)}\s*=\s*\w+\([^)]*task_id\s*=\s*['"]([^'"]+)['"]""",
            source,
            re.DOTALL,
        )
        task_id = task_id_match.group(1) if task_id_match else var_name

        sql_match = re.search(
            rf"""{re.escape(var_name)}\s*=\s*\w+\([^)]*sql\s*=\s*['\"](.*?)['\"]""",
            source,
            re.DOTALL,
        )
        sql_value = sql_match.group(1) if sql_match else ""

        tasks.append({
            "variable": var_name,
            "task_id": task_id,
            "operator_class": operator_class,
            "sql": sql_value,
            "source_file": source_file,
        })

    with_dag_pattern = re.compile(
        r"""(\w+)\s*=\s*(\w+)\s*\(\s*task_id\s*=\s*['"]([^'"]+)['"]""",
        re.MULTILINE,
    )
    existing_vars = {t["variable"] for t in tasks}
    for match in with_dag_pattern.finditer(source):
        var_name = match.group(1)
        if var_name in existing_vars:
            continue
        cls = match.group(2)
        tid = match.group(3)
        tasks.append({
            "variable": var_name,
            "task_id": tid,
            "operator_class": cls,
            "sql": "",
            "source_file": source_file,
        })

    return tasks


def _extract_dependencies(source: str) -> list[tuple[str, str]]:
    """Extract >> and << dependency chains."""
    deps: list[tuple[str, str]] = []
    # a >> b >> c  or  [a, b] >> c
    chain_pattern = re.compile(r"""([\w\[\], ]+)\s*>>\s*([\w\[\], ]+)""")
    for match in chain_pattern.finditer(source):
        upstreams = _parse_task_refs(match.group(1))
        downstreams = _parse_task_refs(match.group(2))
        for u in upstreams:
            for d in downstreams:
                deps.append((u, d))
    return deps


def _parse_task_refs(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1]
        return [t.strip() for t in inner.split(",") if t.strip()]
    return [text] if text else []


def _task_to_lineage(
    task: dict, source_file: str
) -> tuple[list[DatasetNode], list[TransformationNode]]:
    datasets: list[DatasetNode] = []
    transforms: list[TransformationNode] = []

    sql = task.get("sql", "")
    if sql:
        from src.analyzers.sql_lineage import parse_sql_string

        sql_transforms = parse_sql_string(sql, source_file=source_file)
        transforms.extend(sql_transforms)

    op_class = task.get("operator_class", "").lower()
    if "python" in op_class:
        transforms.append(
            TransformationNode(
                name=f"airflow_task:{task['task_id']}",
                transformation_type=TransformationType.AIRFLOW_TASK,
                source_file=source_file,
                description=f"PythonOperator task '{task['task_id']}'",
            )
        )
    elif "sql" in op_class or "postgres" in op_class or "mysql" in op_class:
        transforms.append(
            TransformationNode(
                name=f"airflow_task:{task['task_id']}",
                transformation_type=TransformationType.AIRFLOW_TASK,
                source_file=source_file,
                sql_query=sql[:500] if sql else "",
                description=f"SQL operator task '{task['task_id']}'",
            )
        )
    elif "bash" in op_class:
        transforms.append(
            TransformationNode(
                name=f"airflow_task:{task['task_id']}",
                transformation_type=TransformationType.AIRFLOW_TASK,
                source_file=source_file,
                description=f"BashOperator task '{task['task_id']}'",
            )
        )

    return datasets, transforms


# ---------------------------------------------------------------------------
# dbt YAML parsing
# ---------------------------------------------------------------------------


def parse_dbt_schema(path: str | Path) -> dict[str, Any]:
    """Parse a dbt schema.yml file and extract model/source definitions."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        data = yaml.safe_load(text)
    except Exception as exc:
        logger.warning("Cannot parse dbt schema %s: %s", path, exc)
        return {}

    if not isinstance(data, dict):
        return {}

    result: dict[str, Any] = {
        "models": [],
        "sources": [],
        "datasets": [],
        "source_file": str(path),
    }

    for model in data.get("models", []):
        if isinstance(model, dict):
            result["models"].append({
                "name": model.get("name", ""),
                "description": model.get("description", ""),
                "columns": [
                    c.get("name", "") for c in model.get("columns", [])
                    if isinstance(c, dict)
                ],
            })
            result["datasets"].append(
                DatasetNode(
                    name=model.get("name", ""),
                    storage_type=StorageType.TABLE,
                    source_file=str(path),
                )
            )

    for source in data.get("sources", []):
        if isinstance(source, dict):
            source_name = source.get("name", "")
            for table in source.get("tables", []):
                if isinstance(table, dict):
                    table_name = table.get("name", "")
                    full_name = f"{source_name}.{table_name}" if source_name else table_name
                    result["sources"].append({
                        "source_name": source_name,
                        "table_name": table_name,
                        "full_name": full_name,
                    })
                    result["datasets"].append(
                        DatasetNode(
                            name=full_name,
                            storage_type=StorageType.TABLE,
                            is_source_of_truth=True,
                            source_file=str(path),
                        )
                    )

    return result


def parse_dbt_sql_model(path: str | Path) -> dict[str, Any]:
    """Parse a dbt SQL model file and extract ref() / source() dependencies."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Cannot read dbt model %s: %s", path, exc)
        return {}

    refs: list[str] = re.findall(r"""\{\{\s*ref\s*\(\s*['"](\w+)['"]\s*\)\s*\}\}""", text)
    sources: list[tuple[str, str]] = re.findall(
        r"""\{\{\s*source\s*\(\s*['"](\w+)['"]\s*,\s*['"](\w+)['"]\s*\)\s*\}\}""",
        text,
    )

    model_name = path.stem

    return {
        "model_name": model_name,
        "refs": refs,
        "sources": [f"{s[0]}.{s[1]}" for s in sources],
        "source_file": str(path),
        "transformation": TransformationNode(
            name=f"dbt:{model_name}",
            source_datasets=refs + [f"{s[0]}.{s[1]}" for s in sources],
            target_datasets=[model_name],
            transformation_type=TransformationType.DBT_MODEL,
            source_file=str(path),
        ),
    }


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------


def parse_config_file(path: str | Path) -> dict[str, Any]:
    """Auto-detect config type and parse accordingly."""
    path = Path(path)
    suffix = path.suffix.lower()
    name = path.name.lower()

    if suffix == ".py" and _is_airflow_dag_file(path):
        return parse_airflow_dag(path)

    if suffix in (".yaml", ".yml"):
        text = path.read_text(encoding="utf-8", errors="replace")[:2000]
        if "models:" in text or "sources:" in text:
            return parse_dbt_schema(path)
        if "dag" in text.lower() or "airflow" in text.lower():
            return parse_dbt_schema(path)

    if suffix == ".sql":
        text = path.read_text(encoding="utf-8", errors="replace")[:500]
        if "{{" in text and ("ref(" in text or "source(" in text):
            return parse_dbt_sql_model(path)

    return {}
