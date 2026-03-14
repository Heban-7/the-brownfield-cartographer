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
from typing import Callable, Optional

from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


def _noop_trace(agent: str, action: str, detail: str = "", confidence: str = "high") -> None:
    pass


class ArchivistAgent:
    """Produce persistent documentation artifacts from analysis graphs."""

    def __init__(
        self,
        repo_path: str | Path,
        module_graph: Optional[KnowledgeGraph],
        lineage_graph: Optional[KnowledgeGraph],
        output_dir: str | Path,
        trace_callback: Optional[Callable[[str, str, str, str], None]] = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.module_graph = module_graph
        self.lineage_graph = lineage_graph
        self.output_dir = Path(output_dir)
        self._trace = trace_callback or _noop_trace

    def _log(self, action: str, detail: str = "", confidence: str = "high") -> None:
        self._trace("archivist", action, detail, confidence)

    # ------------------------------------------------------------------ #
    # Public entry
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self._log("start", f"output_dir={self.output_dir}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_codebase_md()
        self._write_onboarding_brief()
        self._log("complete", "All artifacts generated")

    # ------------------------------------------------------------------ #
    # CODEBASE.md
    # ------------------------------------------------------------------ #

    def _write_codebase_md(self) -> None:
        path = self.output_dir / "CODEBASE.md"
        self._log("codebase_md_start", f"target={path}")

        arch_overview = self._architecture_overview()
        self._log("architecture_overview", arch_overview[:200] + "..." if len(arch_overview) > 200 else arch_overview)

        critical_path = self._critical_path_modules()
        self._log("critical_path", f"{len(critical_path)} modules", "high" if critical_path else "medium")

        domain_overview = self._domain_overview()
        self._log("domain_overview", f"domains={[d[0] for d in domain_overview]}")

        data_sources, data_sinks = self._data_sources_and_sinks()
        self._log("data_sources_sinks", f"sources={len(data_sources)} sinks={len(data_sinks)}")

        known_debt = self._known_debt()
        scc_count = sum(1 for line in known_debt if line.strip().startswith("- Group"))
        drift_count = sum(1 for line in known_debt if "docstring differs" in line)
        self._log("known_debt", f"circular_groups={scc_count} drift_modules={drift_count}")

        high_velocity = self._high_velocity_files()
        self._log("high_velocity", f"{len(high_velocity)} files with commits in last 30d")

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
        lines.append("## Domain Overview")
        lines.append("")
        if domain_overview:
            for dom, count in domain_overview:
                lines.append(f"- **{dom}**: {count} module(s)")
        else:
            lines.append("- _No domain clustering information available_")
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
        self._log("codebase_md_written", f"path={path} lines={len(lines)}")

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

    def _domain_overview(self) -> list[tuple[str, int]]:
        """Summarise how many modules fell into each inferred domain."""
        if not self.module_graph:
            return []
        counts: dict[str, int] = {}
        for _, data in self.module_graph.graph.nodes(data=True):
            if data.get("node_type") != "ModuleNode":
                continue
            dom = data.get("domain_cluster") or "unassigned"
            counts[dom] = counts.get(dom, 0) + 1
        return sorted(counts.items(), key=lambda x: (-x[1], x[0]))

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
        self._log("onboarding_brief_start", f"target={path}")

        lines: list[str] = []
        lines.append(f"# Onboarding Brief — {self.repo_path.name}")
        lines.append("")
        lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
        lines.append("")
        lines.append("## The Five FDE Day-One Questions")
        lines.append("")

        answers = (
            self.lineage_graph.graph.graph.get("day_one_answers")
            if self.lineage_graph
            else None
        )

        if isinstance(answers, dict):
            self._log("onboarding_brief_source", "used day_one_answers from Semanticist/lineage_graph")
            lines.append("### 1. What is the primary data ingestion path?")
            lines.append(answers.get("primary_ingestion_path", "_No answer produced._"))
            lines.append("")
            lines.append("### 2. What are the 3–5 most critical output datasets/endpoints?")
            lines.append(answers.get("critical_outputs", "_No answer produced._"))
            lines.append("")
            lines.append("### 3. What is the blast radius if the most critical module fails?")
            lines.append(answers.get("blast_radius", "_No answer produced._"))
            lines.append("")
            lines.append("### 4. Where is the business logic concentrated vs. distributed?")
            lines.append(answers.get("logic_distribution", "_No answer produced._"))
            lines.append("")
            lines.append("### 5. What has changed most frequently in the last 90 days?")
            lines.append(answers.get("change_velocity", "_No answer produced._"))
            lines.append("")
            notes = answers.get("notes")
            if notes:
                lines.append("### Additional Notes")
                lines.append(notes)
                lines.append("")
        else:
            self._log("onboarding_brief_source", "scaffold fallback (no day_one_answers)")
            # Fallback scaffold if Semanticist/LLM did not run.
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
        self._log("onboarding_brief_written", f"path={path} lines={len(lines)}")
