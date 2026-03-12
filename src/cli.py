"""CLI entry point for The Brownfield Cartographer."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

app = typer.Typer(
    name="cartographer",
    help="The Brownfield Cartographer — Codebase Intelligence System",
    add_completion=False,
)
console = Console()


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


@app.command()
def analyze(
    repo: str = typer.Argument(..., help="Path to a local repo or a GitHub URL"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory (default: <repo>/.cartography)"),
    skip_llm: bool = typer.Option(False, "--skip-llm", help="Skip LLM-powered analysis (Phases 3-4)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Run the full Cartographer analysis pipeline on a repository."""
    _setup_logging(verbose)

    from src.orchestrator import Orchestrator

    orch = Orchestrator(repo_input=repo, output_dir=output)

    if skip_llm:
        orch.run_interim_pipeline()
    else:
        orch.run_full_pipeline()


@app.command()
def query(
    repo: str = typer.Argument(..., help="Path to analysed repo (must have .cartography/)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Launch the Navigator interactive query agent."""
    _setup_logging(verbose)

    cartography_dir = Path(repo).resolve() / ".cartography"
    if not cartography_dir.exists():
        console.print("[red]No .cartography/ directory found. Run 'analyze' first.[/]")
        raise typer.Exit(1)

    try:
        from src.agents.navigator import NavigatorAgent

        nav = NavigatorAgent(repo_path=repo)
        nav.interactive()
    except ImportError as exc:
        console.print(f"[red]Navigator not available: {exc}[/]")
        raise typer.Exit(1)


@app.command()
def blast_radius(
    repo: str = typer.Argument(..., help="Path to analysed repo"),
    node: str = typer.Argument(..., help="Dataset or module name to check"),
) -> None:
    """Show the blast radius of a module or dataset."""
    _setup_logging(False)

    from src.graph.knowledge_graph import KnowledgeGraph

    lineage_path = Path(repo).resolve() / ".cartography" / "lineage_graph.json"
    if not lineage_path.exists():
        console.print("[red]No lineage_graph.json found. Run 'analyze' first.[/]")
        raise typer.Exit(1)

    kg = KnowledgeGraph.deserialize(lineage_path)
    candidates = [f"dataset:{node}", f"transform:{node}", node]
    downstream: set[str] = set()
    for cid in candidates:
        if kg.has_node(cid):
            downstream = kg.bfs_downstream(cid)
            break

    if not downstream:
        console.print(f"[yellow]No downstream dependencies found for '{node}'[/]")
    else:
        console.print(f"[bold]Blast radius for '{node}': {len(downstream)} downstream node(s)[/]")
        for d in sorted(downstream):
            console.print(f"  → {d}")


@app.command()
def info(
    repo: str = typer.Argument(..., help="Path to analysed repo"),
) -> None:
    """Show a summary of the cartography results."""
    _setup_logging(False)

    from src.graph.knowledge_graph import KnowledgeGraph

    cartography_dir = Path(repo).resolve() / ".cartography"
    if not cartography_dir.exists():
        console.print("[red]No .cartography/ directory found. Run 'analyze' first.[/]")
        raise typer.Exit(1)

    for name in ("module_graph.json", "lineage_graph.json", "combined_graph.json"):
        gpath = cartography_dir / name
        if gpath.exists():
            kg = KnowledgeGraph.deserialize(gpath)
            console.print(f"\n[bold]{name}[/]")
            for k, v in kg.summary().items():
                console.print(f"  {k}: {v}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
