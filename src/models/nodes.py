"""Pydantic node schemas for the Cartographer knowledge graph."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Language(str, Enum):
    PYTHON = "python"
    SQL = "sql"
    YAML = "yaml"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    UNKNOWN = "unknown"


class StorageType(str, Enum):
    TABLE = "table"
    FILE = "file"
    STREAM = "stream"
    API = "api"
    UNKNOWN = "unknown"


class TransformationType(str, Enum):
    SQL_QUERY = "sql_query"
    PYTHON_TRANSFORM = "python_transform"
    SPARK_JOB = "spark_job"
    DBT_MODEL = "dbt_model"
    AIRFLOW_TASK = "airflow_task"
    UNKNOWN = "unknown"


class ModuleNode(BaseModel):
    """Represents a source file / module in the codebase."""

    path: str
    language: Language = Language.UNKNOWN
    purpose_statement: str = ""
    domain_cluster: str = ""
    complexity_score: float = 0.0
    lines_of_code: int = 0
    comment_ratio: float = 0.0
    change_velocity_30d: int = 0
    is_dead_code_candidate: bool = False
    last_modified: Optional[datetime] = None
    imports: list[str] = Field(default_factory=list)
    public_functions: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    decorators: list[str] = Field(default_factory=list)
    docstring: str = ""


class DatasetNode(BaseModel):
    """Represents a data asset (table, file, stream, API endpoint)."""

    name: str
    storage_type: StorageType = StorageType.UNKNOWN
    schema_snapshot: dict = Field(default_factory=dict)
    freshness_sla: str = ""
    owner: str = ""
    is_source_of_truth: bool = False
    source_file: str = ""
    line_number: int = 0


class FunctionNode(BaseModel):
    """Represents a function or method within a module."""

    qualified_name: str
    parent_module: str
    signature: str = ""
    purpose_statement: str = ""
    call_count_within_repo: int = 0
    is_public_api: bool = True
    line_start: int = 0
    line_end: int = 0
    docstring: str = ""
    decorators: list[str] = Field(default_factory=list)
    complexity_score: float = 0.0


class TransformationNode(BaseModel):
    """Represents a data transformation step linking source to target datasets."""

    name: str
    source_datasets: list[str] = Field(default_factory=list)
    target_datasets: list[str] = Field(default_factory=list)
    transformation_type: TransformationType = TransformationType.UNKNOWN
    source_file: str = ""
    line_start: int = 0
    line_end: int = 0
    sql_query: str = ""
    description: str = ""
