"""Surveyor Agent -- builds the structural skeleton of a codebase.

Performs deep static analysis using tree-sitter, constructs the module import
graph, computes PageRank / circular dependencies, identifies dead code
candidates, and merges git velocity data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from rich.progress import Progress, SpinnerColumn, TextColumn

from src.analyzers.git_analyzer import extract_git_velocity
from src.analyzers.tree_sitter_analyzer import (
    analyze_module,
    extract_functions,
    language_for_file,
)
from src.graph.knowledge_graph import KnowledgeGraph
from src.models.edges import ImportsEdge
from src.models.nodes import FunctionNode, ModuleNode

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".tox", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", "dist", "build", "egg-info",
    ".cartography", ".eggs",
}

SUPPORTED_EXTENSIONS = {".py", ".sql", ".yaml", ".yml"}


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & SKIP_DIRS)


def _collect_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for p in repo_path.rglob("*"):
        if not p.is_file():
            continue
        if _should_skip(p):
            continue
        if p.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(p)
    return sorted(files)


def _resolve_import(
    import_name: str, module_path: Path, repo_path: Path
) -> Optional[str]:
    """Best-effort resolution of a Python import to a file in the repo."""
    parts = import_name.replace(".", "/")
    candidates = [
        repo_path / f"{parts}.py",
        repo_path / parts / "__init__.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                rel = str(candidate.relative_to(repo_path))
                return rel.replace("\\", "/")
            except ValueError:
                return str(candidate).replace("\\", "/")
    return None


class SurveyorAgent:
    """Analyses a repository and produces the module import graph."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        self.kg = KnowledgeGraph()
        self.module_nodes: dict[str, ModuleNode] = {}
        self.function_nodes: dict[str, FunctionNode] = {}

    def run(self) -> KnowledgeGraph:
        """Execute the full survey pipeline."""
        logger.info("Surveyor: scanning %s", self.repo_path)

        files = _collect_files(self.repo_path)
        logger.info("Surveyor: found %d files to analyse", len(files))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Analysing modules...", total=len(files))
            for fp in files:
                self._analyse_file(fp)
                progress.advance(task)

        self._build_import_edges()
        self._compute_git_velocity()
        self._compute_pagerank()
        self._detect_dead_code()
        self._detect_circular_deps()

        logger.info(
            "Surveyor complete: %d nodes, %d edges",
            self.kg.node_count,
            self.kg.edge_count,
        )
        return self.kg

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _analyse_file(self, fp: Path) -> None:
        rel = str(fp.relative_to(self.repo_path)).replace("\\", "/")
        mod = analyze_module(fp)
        if mod is None:
            return
        mod.path = rel
        self.module_nodes[rel] = mod
        self.kg.add_node(rel, mod, node_type="ModuleNode")

        if fp.suffix == ".py":
            for fn in extract_functions(fp):
                fn.parent_module = rel
                fid = f"{rel}::{fn.qualified_name}"
                self.function_nodes[fid] = fn
                self.kg.add_node(fid, fn, node_type="FunctionNode")

    def _build_import_edges(self) -> None:
        for rel, mod in self.module_nodes.items():
            for imp in mod.imports:
                target = _resolve_import(imp, self.repo_path / rel, self.repo_path)
                if target and target in self.module_nodes:
                    edge = ImportsEdge(source=rel, target=target, import_names=[imp])
                    self.kg.add_edge(rel, target, edge=edge, edge_type="IMPORTS")

    def _compute_git_velocity(self) -> None:
        velocity = extract_git_velocity(self.repo_path, days=30)
        for rel, mod in self.module_nodes.items():
            count = velocity.get(rel, 0)
            mod.change_velocity_30d = count
            if self.kg.has_node(rel):
                self.kg.graph.nodes[rel]["change_velocity_30d"] = count

    def _compute_pagerank(self) -> None:
        if self.kg.node_count == 0:
            return
        try:
            pr = self.kg.pagerank()
            for nid, score in pr.items():
                if nid in self.module_nodes:
                    data = self.kg.get_node(nid)
                    if data and data.get("node_type") == "ModuleNode":
                        self.kg.graph.nodes[nid]["pagerank"] = score
        except Exception as exc:
            logger.warning("PageRank computation failed: %s", exc)

    def _detect_dead_code(self) -> None:
        imported_targets: set[str] = set()
        for _, _, data in self.kg.edges_by_type("IMPORTS"):
            imported_targets.add(data.get("target", ""))

        for rel, mod in self.module_nodes.items():
            if rel not in imported_targets and not rel.endswith("__init__.py"):
                mod.is_dead_code_candidate = True
                if self.kg.has_node(rel):
                    self.kg.graph.nodes[rel]["is_dead_code_candidate"] = True

    def _detect_circular_deps(self) -> None:
        sccs = self.kg.strongly_connected_components()
        if sccs:
            logger.warning(
                "Surveyor: detected %d circular dependency group(s)", len(sccs)
            )
            for i, scc in enumerate(sccs):
                for nid in scc:
                    if self.kg.has_node(nid):
                        self.kg.graph.nodes[nid]["circular_dep_group"] = i

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def top_modules_by_pagerank(self, n: int = 10) -> list[tuple[str, float]]:
        pr = {
            nid: data.get("pagerank", 0.0)
            for nid, data in self.kg.graph.nodes(data=True)
            if data.get("node_type") == "ModuleNode"
        }
        return sorted(pr.items(), key=lambda x: x[1], reverse=True)[:n]

    def circular_dependency_groups(self) -> list[set[str]]:
        return self.kg.strongly_connected_components()

    def dead_code_candidates(self) -> list[str]:
        return [
            rel for rel, mod in self.module_nodes.items()
            if mod.is_dead_code_candidate
        ]
