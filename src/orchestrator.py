"""Orchestrator -- wires agents in sequence and manages .cartography/ output."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel

from src.agents.surveyor import SurveyorAgent
from src.agents.hydrologist import HydrologistAgent
from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)
console = Console()


def _clone_if_url(repo_input: str) -> Path:
    """If *repo_input* looks like a URL, clone it to a temp directory."""
    if repo_input.startswith("http://") or repo_input.startswith("https://") or repo_input.startswith("git@"):
        dest = Path(tempfile.mkdtemp(prefix="cartographer_"))
        console.print(f"[bold cyan]Cloning {repo_input} …[/]")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_input, str(dest)],
            check=True,
            capture_output=True,
        )
        console.print(f"[green]Cloned to {dest}[/]")
        return dest
    return Path(repo_input).resolve()


class Orchestrator:
    """Runs the Cartographer pipeline and writes artefacts to .cartography/."""

    def __init__(
        self,
        repo_input: str,
        output_dir: Optional[str] = None,
        incremental: bool = False,
    ):
        self.repo_path = _clone_if_url(repo_input)
        self.output_dir = Path(output_dir) if output_dir else (self.repo_path / ".cartography")
        self.incremental = incremental
        self.module_graph: Optional[KnowledgeGraph] = None
        self.lineage_graph: Optional[KnowledgeGraph] = None
        self.combined_graph: Optional[KnowledgeGraph] = None
        self.trace: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Trace logging
    # ------------------------------------------------------------------

    def _log_trace(self, agent: str, action: str, detail: str = "", confidence: str = "high") -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "detail": detail,
            "confidence": confidence,
        }
        self.trace.append(entry)

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def run_survey(self) -> KnowledgeGraph:
        console.print(Panel("[bold]Stage 1/4: Surveyor Agent[/] — Static Structure Analysis"))
        start = time.time()
        surveyor = SurveyorAgent(self.repo_path)
        self.module_graph = surveyor.run()
        elapsed = time.time() - start

        self._log_trace("surveyor", "complete", f"{self.module_graph.node_count} nodes in {elapsed:.1f}s")

        top_modules = surveyor.top_modules_by_pagerank(5)
        if top_modules:
            console.print("[bold]Top modules by PageRank:[/]")
            for mod, score in top_modules:
                console.print(f"  {mod}  (score={score:.4f})")

        circular = surveyor.circular_dependency_groups()
        if circular:
            console.print(f"[yellow]⚠ {len(circular)} circular dependency group(s) detected[/]")

        dead = surveyor.dead_code_candidates()
        if dead:
            console.print(f"[dim]{len(dead)} dead-code candidate(s)[/]")

        return self.module_graph

    def run_hydrology(self) -> KnowledgeGraph:
        console.print(Panel("[bold]Stage 2/4: Hydrologist Agent[/] — Data Lineage Analysis"))
        start = time.time()
        hydro = HydrologistAgent(self.repo_path)
        self.lineage_graph = hydro.run()
        elapsed = time.time() - start

        self._log_trace("hydrologist", "complete", f"{self.lineage_graph.node_count} nodes in {elapsed:.1f}s")

        sources = hydro.find_sources()
        sinks = hydro.find_sinks()
        console.print(f"[bold]Data sources:[/] {len(sources)}")
        for s in sources[:10]:
            console.print(f"  {s}")
        console.print(f"[bold]Data sinks:[/] {len(sinks)}")
        for s in sinks[:10]:
            console.print(f"  {s}")

        return self.lineage_graph

    def run_semanticist(self) -> None:
        """Stage 3: LLM-powered semantic analysis (requires API key)."""
        console.print(Panel("[bold]Stage 3/4: Semanticist Agent[/] — LLM-Powered Analysis"))
        try:
            from src.agents.semanticist import SemanticistAgent

            sem = SemanticistAgent(
                repo_path=self.repo_path,
                module_graph=self.module_graph,
                lineage_graph=self.lineage_graph,
            )
            sem.run()
            self._log_trace("semanticist", "complete", "Purpose statements + domain clustering done")
        except Exception as exc:
            console.print(f"[yellow]Semanticist skipped: {exc}[/]")
            self._log_trace("semanticist", "skipped", str(exc), confidence="low")

    def run_archivist(self) -> None:
        """Stage 4: Generate living context artifacts."""
        console.print(Panel("[bold]Stage 4/4: Archivist Agent[/] — Living Context Generation"))
        try:
            from src.agents.archivist import ArchivistAgent

            archivist = ArchivistAgent(
                repo_path=self.repo_path,
                module_graph=self.module_graph,
                lineage_graph=self.lineage_graph,
                output_dir=self.output_dir,
            )
            archivist.run()
            self._log_trace("archivist", "complete", "Artefacts generated")
        except Exception as exc:
            console.print(f"[yellow]Archivist skipped: {exc}[/]")
            self._log_trace("archivist", "skipped", str(exc), confidence="low")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _save_outputs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.module_graph:
            self.module_graph.serialize(self.output_dir / "module_graph.json")

        if self.lineage_graph:
            self.lineage_graph.serialize(self.output_dir / "lineage_graph.json")

        if self.module_graph and self.lineage_graph:
            self.combined_graph = KnowledgeGraph()
            self.combined_graph.merge(self.module_graph)
            self.combined_graph.merge(self.lineage_graph)
            self.combined_graph.serialize(self.output_dir / "combined_graph.json")

        trace_path = self.output_dir / "cartography_trace.jsonl"
        with open(trace_path, "w", encoding="utf-8") as f:
            for entry in self.trace:
                f.write(json.dumps(entry, default=str) + "\n")

        meta = {
            "repo_path": str(self.repo_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module_graph_nodes": self.module_graph.node_count if self.module_graph else 0,
            "lineage_graph_nodes": self.lineage_graph.node_count if self.lineage_graph else 0,
        }
        with open(self.output_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        console.print(f"\n[bold green]Artefacts written to {self.output_dir}/[/]")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_full_pipeline(self, skip_llm: bool = False) -> None:
        """Execute all pipeline stages in sequence."""
        console.print(
            Panel(
                f"[bold magenta]The Brownfield Cartographer[/]\n"
                f"Target: {self.repo_path}",
                title="Cartographer",
            )
        )
        start = time.time()

        self.run_survey()
        self.run_hydrology()

        if not skip_llm:
            self.run_semanticist()
            self.run_archivist()

        self._save_outputs()

        elapsed = time.time() - start
        console.print(f"\n[bold]Total analysis time: {elapsed:.1f}s[/]")
        self._log_trace("orchestrator", "pipeline_complete", f"{elapsed:.1f}s")

    def run_interim_pipeline(self) -> None:
        """Run only Surveyor + Hydrologist (for interim deliverable)."""
        console.print(
            Panel(
                f"[bold magenta]The Brownfield Cartographer[/] (Interim)\n"
                f"Target: {self.repo_path}",
                title="Cartographer",
            )
        )
        start = time.time()

        self.run_survey()
        self.run_hydrology()
        self._save_outputs()

        elapsed = time.time() - start
        console.print(f"\n[bold]Total analysis time: {elapsed:.1f}s[/]")
