"""Archivist Agent — generates living context artifacts.

Outputs:
  - CODEBASE.md
  - onboarding_brief.md
  - cartography_trace.jsonl (appended by orchestrator)

This agent reads the module and lineage graphs (plus any semantic annotations)
and turns them into human-readable docs optimised for AI context injection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class ArchivistAgent:
    """Produce persistent documentation artifacts from analysis graphs."""

    def __init__(
        self,
        repo_path: str | Path,
        module_graph: Optional[KnowledgeGraph],
        lineage_graph: Optional[KnowledgeGraph],
        output_dir: str | Path,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.module_graph = module_graph
        self.lineage_graph = lineage_graph
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------ #
    # Public entry
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_codebase_md()
        self._write_onboarding_brief()

    # ------------------------------------------------------------------ #
    # CODEBASE.md
    # ------------------------------------------------------------------ #

    def _write_codebase_md(self) -> None:
        path = self.output_dir / "CODEBASE.md"

        arch_overview = self._architecture_overview()
        critical_path = self._critical_path_modules()
        data_sources, data_sinks = self._data_sources_and_sinks()
        known_debt = self._known_debt()
        high_velocity = self._high_velocity_files()

        lines: list[str] = []
        lines.append(f"# CODEBASE — {self.repo_path.name}")
        lines.append("")
        lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
        lines.append("")
        lines.append("## Architecture Overview")
        lines.append("")
        lines.append(arch_overview)
        lines.append("")
        lines.append("## Critical Path (Top Modules by PageRank)")
        lines.append("")
        if critical_path:
            for mod, score in critical_path:
                lines.append(f"- `{mod}` (PageRank={score:.4f})")
        else:
            lines.append("_No PageRank data available._")
        lines.append("")
        lines.append("## Data Sources & Sinks")
        lines.append("")
        lines.append("### Sources (entry points)")
        if data_sources:
            for s in data_sources[:50]:
                lines.append(f"- `{s}`")
        else:
            lines.append("- _No sources detected_")
        lines.append("")
        lines.append("### Sinks (terminal outputs)")
        if data_sinks:
            for s in data_sinks[:50]:
                lines.append(f"- `{s}`")
        else:
            lines.append("- _No sinks detected_")
        lines.append("")
        lines.append("## Known Debt")
        lines.append("")
        lines.extend(known_debt or ["- _No known structural debt recorded_"])
        lines.append("")
        lines.append("## High-Velocity Files (last 30 days)")
        lines.append("")
        if high_velocity:
            for path_rel, count in high_velocity:
                lines.append(f"- `{path_rel}` — {count} commits")
        else:
            lines.append("- _Git velocity data unavailable_")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Archivist: wrote %s", path)

    def _architecture_overview(self) -> str:
        if not self.module_graph:
            return "Static analysis graph not available."

        summary = self.module_graph.summary()
        total_nodes = summary.get("total_nodes", 0)
        total_edges = summary.get("total_edges", 0)
        node_types = summary.get("node_types", {})
        edge_types = summary.get("edge_types", {})

        parts: list[str] = []
        parts.append(
            f"The repository `{self.repo_path.name}` contains {total_nodes} nodes "
            f"and {total_edges} edges in the combined knowledge graph."
        )
        if node_types:
            parts.append(
                "Node composition: "
                + ", ".join(f"{k}={v}" for k, v in sorted(node_types.items()))
            )
        if edge_types:
            parts.append(
                "Edge composition: "
                + ", ".join(f"{k}={v}" for k, v in sorted(edge_types.items()))
            )
        return " ".join(parts)

    def _critical_path_modules(self, n: int = 5) -> list[tuple[str, float]]:
        if not self.module_graph:
            return []
        pr = {
            nid: data.get("pagerank", 0.0)
            for nid, data in self.module_graph.graph.nodes(data=True)
            if data.get("node_type") == "ModuleNode"
        }
        if not pr:
            return []
        return sorted(pr.items(), key=lambda x: x[1], reverse=True)[:n]

    def _data_sources_and_sinks(self) -> tuple[list[str], list[str]]:
        if not self.lineage_graph:
            return [], []

        sources: list[str] = []
        sinks: list[str] = []
        for nid, data in self.lineage_graph.graph.nodes(data=True):
            if data.get("node_type") != "DatasetNode":
                continue
            indeg = self.lineage_graph.graph.in_degree(nid)
            outdeg = self.lineage_graph.graph.out_degree(nid)
            if indeg == 0:
                sources.append(nid)
            if outdeg == 0:
                sinks.append(nid)
        return sorted(sources), sorted(sinks)

    def _known_debt(self) -> list[str]:
        lines: list[str] = []
        if self.module_graph:
            sccs = self.module_graph.strongly_connected_components()
            if sccs:
                lines.append("### Circular dependencies")
                for i, comp in enumerate(sccs, start=1):
                    members = ", ".join(sorted(comp))
                    lines.append(f"- Group {i}: {members}")
                lines.append("")

            drifted = [
                nid
                for nid, data in self.module_graph.graph.nodes(data=True)
                if data.get("doc_drift")
            ]
            if drifted:
                lines.append("### Documentation drift")
                for nid in sorted(drifted):
                    lines.append(f"- `{nid}` (docstring differs from implementation)")
                lines.append("")

        return lines

    def _high_velocity_files(self) -> list[tuple[str, int]]:
        if not self.module_graph:
            return []
        items: list[tuple[str, int]] = []
        for nid, data in self.module_graph.graph.nodes(data=True):
            if data.get("node_type") == "ModuleNode":
                count = int(data.get("change_velocity_30d", 0))
                if count > 0:
                    items.append((nid, count))
        return sorted(items, key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------ #
    # onboarding_brief.md
    # ------------------------------------------------------------------ #

    def _write_onboarding_brief(self) -> None:
        path = self.output_dir / "onboarding_brief.md"

        lines: list[str] = []
        lines.append(f"# Onboarding Brief — {self.repo_path.name}")
        lines.append("")
        lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
        lines.append("")
        lines.append("## The Five FDE Day-One Questions")
        lines.append("")
        lines.append("### 1. What is the primary data ingestion path?")
        lines.append("- _To be refined via Semanticist/Navigator; initial hints from data sources in `CODEBASE.md`._")
        lines.append("")
        lines.append("### 2. What are the 3–5 most critical output datasets/endpoints?")
        lines.append("- _See Data Sinks section in `CODEBASE.md`; sort by business importance once known._")
        lines.append("")
        lines.append("### 3. What is the blast radius if the most critical module fails?")
        lines.append("- _Use the `cartographer blast-radius` CLI on candidate modules/datasets._")
        lines.append("")
        lines.append("### 4. Where is the business logic concentrated vs. distributed?")
        lines.append("- _Approximate via high PageRank modules and domain clusters (if Semanticist ran)._")
        lines.append("")
        lines.append("### 5. What has changed most frequently in the last 90 days?")
        lines.append("- _See High-Velocity Files section in `CODEBASE.md`._")
        lines.append("")
        lines.append("> NOTE: This brief is a scaffold; for a full answer you will typically")
        lines.append("> re-run the Semanticist with appropriate API keys and use the Navigator")
        lines.append("> agent to cross-check answers against specific files and line ranges.")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Archivist: wrote %s", path)

