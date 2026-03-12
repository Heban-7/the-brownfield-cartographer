"""SQL lineage extraction using sqlglot.

Parses .sql files (and SQL embedded in dbt models) to extract the full table
dependency graph from SELECT / FROM / JOIN / WITH (CTE) chains.  Supports
PostgreSQL, BigQuery, Snowflake, and DuckDB dialects.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import sqlglot
from sqlglot import exp

from src.models.nodes import TransformationNode, TransformationType

logger = logging.getLogger(__name__)

SUPPORTED_DIALECTS = ("postgres", "bigquery", "snowflake", "duckdb", None)


def _extract_tables_from_expression(expression: exp.Expression) -> set[str]:
    """Walk an sqlglot AST and collect all referenced table names."""
    tables: set[str] = set()
    for table in expression.find_all(exp.Table):
        parts = []
        if table.catalog:
            parts.append(table.catalog)
        if table.db:
            parts.append(table.db)
        if table.name:
            parts.append(table.name)
        if parts:
            tables.add(".".join(parts))
    return tables


def _extract_cte_names(expression: exp.Expression) -> set[str]:
    """Return names defined as CTEs so we can exclude them from source tables."""
    ctes: set[str] = set()
    for cte in expression.find_all(exp.CTE):
        alias = cte.args.get("alias")
        if alias:
            ctes.add(alias.name if hasattr(alias, "name") else str(alias))
    return ctes


def _extract_target_tables(expression: exp.Expression) -> set[str]:
    """Extract target tables from INSERT / CREATE / MERGE statements."""
    targets: set[str] = set()

    if isinstance(expression, exp.Insert):
        table = expression.find(exp.Table)
        if table and table.name:
            targets.add(table.name)

    if isinstance(expression, exp.Create):
        table = expression.find(exp.Table)
        if table and table.name:
            targets.add(table.name)

    return targets


def parse_sql_file(
    path: str | Path,
    dialect: Optional[str] = None,
) -> list[TransformationNode]:
    """Parse a SQL file and return TransformationNode(s) capturing lineage.

    Each SQL statement in the file becomes one TransformationNode whose
    *source_datasets* are the tables read (FROM / JOIN) and whose
    *target_datasets* are the tables written (INSERT / CREATE) -- or the
    filename stem when no explicit target exists (common for dbt models
    that are defined as SELECT statements).
    """
    path = Path(path)
    try:
        sql_text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning("Cannot read SQL file %s: %s", path, exc)
        return []

    if not sql_text.strip():
        return []

    transformations: list[TransformationNode] = []
    parsed_any = False

    for try_dialect in (dialect,) if dialect else SUPPORTED_DIALECTS:
        try:
            statements = sqlglot.parse(sql_text, read=try_dialect, error_level=sqlglot.ErrorLevel.WARN)
            parsed_any = True
        except Exception:
            continue

        for stmt in statements:
            if stmt is None:
                continue

            all_tables = _extract_tables_from_expression(stmt)
            cte_names = _extract_cte_names(stmt)
            source_tables = all_tables - cte_names

            target_tables = _extract_target_tables(stmt)
            if not target_tables:
                target_tables = {path.stem}

            source_tables -= target_tables

            if source_tables or target_tables:
                transformations.append(
                    TransformationNode(
                        name=f"sql:{path.stem}",
                        source_datasets=sorted(source_tables),
                        target_datasets=sorted(target_tables),
                        transformation_type=TransformationType.SQL_QUERY,
                        source_file=str(path),
                        sql_query=sql_text[:500],
                    )
                )

        if parsed_any:
            break

    if not parsed_any:
        logger.warning("Could not parse SQL in %s with any dialect", path)

    return transformations


def parse_sql_string(
    sql: str,
    source_file: str = "<inline>",
    dialect: Optional[str] = None,
) -> list[TransformationNode]:
    """Parse a raw SQL string and return lineage TransformationNodes."""
    transformations: list[TransformationNode] = []

    for try_dialect in (dialect,) if dialect else SUPPORTED_DIALECTS:
        try:
            statements = sqlglot.parse(sql, read=try_dialect, error_level=sqlglot.ErrorLevel.WARN)
        except Exception:
            continue

        for stmt in statements:
            if stmt is None:
                continue
            all_tables = _extract_tables_from_expression(stmt)
            cte_names = _extract_cte_names(stmt)
            source_tables = all_tables - cte_names
            target_tables = _extract_target_tables(stmt)
            source_tables -= target_tables

            if source_tables or target_tables:
                transformations.append(
                    TransformationNode(
                        name=f"sql:{source_file}",
                        source_datasets=sorted(source_tables),
                        target_datasets=sorted(target_tables),
                        transformation_type=TransformationType.SQL_QUERY,
                        source_file=source_file,
                        sql_query=sql[:500],
                    )
                )
        break

    return transformations


def extract_table_dependencies(path: str | Path, dialect: Optional[str] = None) -> dict:
    """Convenience: return a dict with source_tables and target_tables for a SQL file."""
    transforms = parse_sql_file(path, dialect=dialect)
    sources: set[str] = set()
    targets: set[str] = set()
    for t in transforms:
        sources.update(t.source_datasets)
        targets.update(t.target_datasets)
    return {"source_tables": sorted(sources), "target_tables": sorted(targets)}
