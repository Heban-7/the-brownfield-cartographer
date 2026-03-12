"""Pydantic edge schemas for the Cartographer knowledge graph."""

from __future__ import annotations

from pydantic import BaseModel


class ImportsEdge(BaseModel):
    """Module A imports Module B."""

    source: str
    target: str
    import_count: int = 1
    import_names: list[str] = []


class ProducesEdge(BaseModel):
    """Transformation produces a dataset (data lineage output)."""

    source: str  # transformation node id
    target: str  # dataset node id
    source_file: str = ""
    line_range: str = ""


class ConsumesEdge(BaseModel):
    """Transformation consumes a dataset (upstream dependency)."""

    source: str  # transformation node id
    target: str  # dataset node id
    source_file: str = ""
    line_range: str = ""


class CallsEdge(BaseModel):
    """Function A calls Function B."""

    source: str
    target: str
    call_count: int = 1
    source_file: str = ""
    line_number: int = 0


class ConfiguresEdge(BaseModel):
    """Config file configures a module or pipeline."""

    source: str  # config file path
    target: str  # module / pipeline id
    config_keys: list[str] = []
