"""Hydrologist Agent -- constructs the data lineage DAG.

Merges SQL lineage (sqlglot), Airflow/dbt config parsing, and Python data-flow
detection into a unified DataLineageGraph.  Provides blast_radius, trace_upstream,
find_sources, and find_sinks queries.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from rich.progress import Progress, SpinnerColumn, TextColumn

from src.analyzers.dag_config_parser import (
    parse_airflow_dag,
    parse_config_file,
    parse_dbt_sql_model,
)
from src.analyzers.sql_lineage import parse_sql_file
from src.analyzers.tree_sitter_analyzer import extract_data_references
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.edges import ConsumesEdge, ProducesEdge
from src.models.nodes import (
    DatasetNode,
    StorageType,
    TransformationNode,
    TransformationType,
)

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".tox", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "dist", "build", "egg-info",
    ".cartography", ".eggs",
}


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & SKIP_DIRS)


class HydrologistAgent:
    """Builds the data lineage graph for a repository."""

    def __init__(self, repo_path: str | Path, changed_files: Optional[list[Path]] = None):
        self.repo_path = Path(repo_path).resolve()
        self.kg = KnowledgeGraph()
        self.datasets: dict[str, DatasetNode] = {}
        self.transformations: list[TransformationNode] = []
        self._changed_files = changed_files

    def run(self) -> KnowledgeGraph:
        """Execute the full lineage analysis pipeline."""
        logger.info("Hydrologist: scanning %s", self.repo_path)

        files = self._collect_files()
        logger.info("Hydrologist: found %d files to analyse", len(files))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Analysing data lineage...", total=len(files))
            for fp in files:
                self._analyse_file(fp)
                progress.advance(task)

        self._build_lineage_graph()

        logger.info(
            "Hydrologist complete: %d nodes, %d edges",
            self.kg.node_count,
            self.kg.edge_count,
        )
        return self.kg

    # ------------------------------------------------------------------
    # File collection
    # ------------------------------------------------------------------

    def _collect_files(self) -> list[Path]:
        if self._changed_files:
            logger.info("Hydrologist: incremental mode, %d changed file(s)", len(self._changed_files))
            return sorted(self._changed_files)

        files: list[Path] = []
        for p in self.repo_path.rglob("*"):
            if not p.is_file():
                continue
            if _should_skip(p):
                continue
            if p.suffix.lower() in {".py", ".sql", ".yaml", ".yml"}:
                files.append(p)
        return sorted(files)

    # ------------------------------------------------------------------
    # Per-file analysis
    # ------------------------------------------------------------------

    def _analyse_file(self, fp: Path) -> None:
        suffix = fp.suffix.lower()

        if suffix == ".sql":
            self._analyse_sql(fp)

        if suffix == ".py":
            self._analyse_python(fp)

        if suffix in (".yaml", ".yml"):
            self._analyse_yaml(fp)

        if suffix == ".sql":
            text = fp.read_text(encoding="utf-8", errors="replace")[:500]
            if "{{" in text and ("ref(" in text or "source(" in text):
                self._analyse_dbt_model(fp)

    def _analyse_sql(self, fp: Path) -> None:
        transforms = parse_sql_file(fp)
        self.transformations.extend(transforms)

    def _analyse_python(self, fp: Path) -> None:
        data_refs = extract_data_references(fp)
        for ds in data_refs:
            self._register_dataset(ds)

        config = parse_config_file(fp)
        if config:
            for t in config.get("transformations", []):
                if isinstance(t, TransformationNode):
                    self.transformations.append(t)
            for ds in config.get("datasets", []):
                if isinstance(ds, DatasetNode):
                    self._register_dataset(ds)

            for dep in config.get("dependencies", []):
                if isinstance(dep, tuple) and len(dep) == 2:
                    upstream, downstream = dep
                    dag_id = config.get("dag_id", "")
                    t = TransformationNode(
                        name=f"airflow_dep:{dag_id}:{upstream}->{downstream}",
                        transformation_type=TransformationType.AIRFLOW_TASK,
                        source_file=str(fp),
                        description=f"Airflow dependency: {upstream} >> {downstream}",
                    )
                    self.transformations.append(t)

    def _analyse_yaml(self, fp: Path) -> None:
        config = parse_config_file(fp)
        if config:
            for ds in config.get("datasets", []):
                if isinstance(ds, DatasetNode):
                    self._register_dataset(ds)

    def _analyse_dbt_model(self, fp: Path) -> None:
        result = parse_dbt_sql_model(fp)
        if result and "transformation" in result:
            self.transformations.append(result["transformation"])

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _register_dataset(self, ds: DatasetNode) -> None:
        if ds.name not in self.datasets:
            self.datasets[ds.name] = ds

    def _build_lineage_graph(self) -> None:
        for name, ds in self.datasets.items():
            self.kg.add_node(f"dataset:{name}", ds, node_type="DatasetNode")

        for t in self.transformations:
            tid = f"transform:{t.name}"
            self.kg.add_node(tid, t, node_type="TransformationNode")

            for src in t.source_datasets:
                dsid = f"dataset:{src}"
                if not self.kg.has_node(dsid):
                    auto_ds = DatasetNode(name=src, storage_type=StorageType.TABLE)
                    self.kg.add_node(dsid, auto_ds, node_type="DatasetNode")

                edge = ConsumesEdge(
                    source=tid, target=dsid, source_file=t.source_file
                )
                self.kg.add_edge(dsid, tid, edge=edge, edge_type="CONSUMES")

            for tgt in t.target_datasets:
                dsid = f"dataset:{tgt}"
                if not self.kg.has_node(dsid):
                    auto_ds = DatasetNode(name=tgt, storage_type=StorageType.TABLE)
                    self.kg.add_node(dsid, auto_ds, node_type="DatasetNode")

                edge = ProducesEdge(
                    source=tid, target=dsid, source_file=t.source_file
                )
                self.kg.add_edge(tid, dsid, edge=edge, edge_type="PRODUCES")

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def blast_radius(self, node_name: str) -> set[str]:
        """Return all downstream dependents of a dataset or transformation."""
        candidates = [
            f"dataset:{node_name}",
            f"transform:{node_name}",
            node_name,
        ]
        for cid in candidates:
            if self.kg.has_node(cid):
                return self.kg.bfs_downstream(cid)
        return set()

    def trace_upstream(self, node_name: str) -> set[str]:
        """Return all upstream ancestors of a dataset or transformation."""
        candidates = [
            f"dataset:{node_name}",
            f"transform:{node_name}",
            node_name,
        ]
        for cid in candidates:
            if self.kg.has_node(cid):
                return self.kg.bfs_upstream(cid)
        return set()

    def find_sources(self) -> list[str]:
        """Return dataset nodes with in-degree == 0 (data entry points)."""
        sources = []
        for nid, data in self.kg.nodes_by_type("DatasetNode"):
            if self.kg.graph.in_degree(nid) == 0:
                sources.append(nid)
        return sorted(sources)

    def find_sinks(self) -> list[str]:
        """Return dataset nodes with out-degree == 0 (terminal outputs)."""
        sinks = []
        for nid, data in self.kg.nodes_by_type("DatasetNode"):
            if self.kg.graph.out_degree(nid) == 0:
                sinks.append(nid)
        return sorted(sinks)
