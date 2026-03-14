"""Navigator Agent — query interface over the knowledge graph.

This is intentionally lightweight: it loads the serialized graphs from
`.cartography/` and exposes four tools:

  - find_implementation(concept)
  - trace_lineage(dataset, direction)
  - blast_radius(module_path)
  - explain_module(path)

The `interactive()` method provides a simple REPL so you can drive it from
the CLI (`cartographer query <repo>`).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal, Optional

from litellm import completion, embedding
from rich.console import Console
from rich.prompt import Prompt

from src.graph.knowledge_graph import KnowledgeGraph
from src.graph.semantic_index import SemanticIndex

logger = logging.getLogger(__name__)
console = Console()

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
OPENROUTER_EXPLAIN_MODEL_ENV = "OPENROUTER_EXPLAIN_MODEL"
OPENROUTER_EMBED_MODEL_ENV = "OPENROUTER_EMBED_MODEL"


class NavigatorAgent:
    """Simple, REPL-based navigator over the Cartographer graphs."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.cartography_dir = self.repo_path / ".cartography"
        self.module_graph_path = self.cartography_dir / "module_graph.json"
        self.lineage_graph_path = self.cartography_dir / "lineage_graph.json"
        self.combined_graph_path = self.cartography_dir / "combined_graph.json"

        if self.combined_graph_path.exists():
            self.kg = KnowledgeGraph.deserialize(self.combined_graph_path)
        elif self.module_graph_path.exists():
            self.kg = KnowledgeGraph.deserialize(self.module_graph_path)
        else:
            raise RuntimeError("No knowledge graph JSON found under .cartography/")

        # Optional semantic index for vector-based search.
        si_dir = self.cartography_dir / "semantic_index"
        self.semantic_index: Optional[SemanticIndex] = None
        if si_dir.exists():
            try:
                self.semantic_index = SemanticIndex(si_dir)
            except Exception as exc:
                logger.warning("Navigator: could not load semantic index: %s", exc)
        self.embed_model = os.getenv(OPENROUTER_EMBED_MODEL_ENV, "openrouter/openai/text-embedding-3-small")

    # ------------------------------------------------------------------ #
    # Interactive loop
    # ------------------------------------------------------------------ #

    def interactive(self) -> None:
        console.print("[bold]Navigator Agent[/] — type 'help' for options, 'quit' to exit.")
        while True:
            cmd = Prompt.ask("[bold cyan]nav>[/]").strip()
            if not cmd:
                continue
            if cmd.lower() in {"quit", "exit"}:
                break
            if cmd.lower() in {"help", "?"}:
                self._print_help()
                continue
            self._dispatch(cmd)

    def _print_help(self) -> None:
        console.print(
            "\n[bold]Commands:[/]\n"
            "  impl <concept>              — semantic search for implementation\n"
            "  lineage <dataset> <up|down> — trace data lineage\n"
            "  blast <node>                — blast radius for module/dataset\n"
            "  explain <module_path>       — explain a module\n"
            "  help                        — show this help\n"
            "  quit                        — exit\n"
        )

    def _dispatch(self, cmd: str) -> None:
        parts = cmd.split()
        if not parts:
            return
        action = parts[0].lower()
        try:
            if action == "impl" and len(parts) >= 2:
                concept = " ".join(parts[1:])
                self._cmd_find_implementation(concept)
            elif action == "lineage" and len(parts) >= 3:
                dataset = parts[1]
                direction = parts[2].lower()
                self._cmd_trace_lineage(dataset, direction)
            elif action == "blast" and len(parts) >= 2:
                node = " ".join(parts[1:])
                self._cmd_blast_radius(node)
            elif action == "explain" and len(parts) >= 2:
                path = " ".join(parts[1:])
                self._cmd_explain_module(path)
            else:
                # Treat as a natural-language question and route heuristically.
                question = cmd
                self._route_question(question)
        except Exception as exc:
            logger.exception("Navigator command failed: %s", exc)
            console.print(f"[red]Error:[/] {exc}")

    # ------------------------------------------------------------------ #
    # Tools
    # ------------------------------------------------------------------ #

    def _cmd_find_implementation(self, concept: str) -> None:
        """Semantic search for implementation locations.

        Prefer vector-based search over the semantic index; fall back to
        substring search over purpose/docstring if no index is available.
        """
        # Vector-based search when index + embed model are available.
        if self.semantic_index is not None:
            try:
                emb = embedding(model=self.embed_model, input=concept)
                vec = emb["data"][0]["embedding"]
                hits = self.semantic_index.query(vec, k=10)
                if hits:
                    console.print(f"[bold]Semantic matches for '{concept}' (vector search):[/]")
                    for h in hits:
                        mid = h["id"]
                        meta = h.get("metadata") or {}
                        path = meta.get("path", mid)
                        dist = h.get("distance")
                        evidence = self.kg.get_evidence(mid)
                        loc = evidence.get("path") or path
                        ls = evidence.get("line_start")
                        le = evidence.get("line_end")
                        loc_str = f"{loc}:{ls}-{le}" if ls and le else loc
                        console.print(f"- {mid}  [dim]({loc_str}, dist={dist:.3f})[/]")
                    return
            except Exception as exc:
                logger.warning("Navigator: vector search failed, falling back to substring: %s", exc)

        # Fallback: substring search across module path + purpose + docstring.
        matches = []
        c_lower = concept.lower()
        for nid, data in self.kg.graph.nodes(data=True):
            if data.get("node_type") != "ModuleNode":
                continue
            text = " ".join(
                [
                    str(data.get("path") or nid),
                    str(data.get("purpose_statement") or ""),
                    str(data.get("docstring") or ""),
                ]
            ).lower()
            if c_lower in text:
                matches.append(nid)

        if not matches:
            console.print(f"[yellow]No modules mentioning '{concept}'.[/]")
            return

        console.print(f"[bold]Modules related to '{concept}' (substring search):[/]")
        for nid in matches[:20]:
            evidence = self.kg.get_evidence(nid)
            path = evidence.get("path") or nid
            ls = evidence.get("line_start")
            le = evidence.get("line_end")
            loc = f"{path}:{ls}-{le}" if ls and le else path
            console.print(f"- {nid}  [dim]({loc})[/]")

    def _cmd_trace_lineage(self, dataset: str, direction: str) -> None:
        kg = self._load_lineage_graph()
        candidates = [f"dataset:{dataset}", dataset]
        start = None
        for cid in candidates:
            if kg.has_node(cid):
                start = cid
                break
        if not start:
            console.print(f"[yellow]Dataset '{dataset}' not found in lineage graph.[/]")
            return

        if direction.startswith("up"):
            nodes = kg.bfs_upstream(start)
            label = "upstream"
        else:
            nodes = kg.bfs_downstream(start)
            label = "downstream"

        console.print(f"[bold]{label.capitalize()} lineage for '{dataset}' ({len(nodes)} nodes):[/]")
        for nid in sorted(nodes):
            evidence = kg.get_evidence(nid)
            path = evidence.get("path") or nid
            ls = evidence.get("line_start")
            le = evidence.get("line_end")
            loc = f"{path}:{ls}-{le}" if ls and le else path
            console.print(f"- {nid}  [dim]({loc})[/]")

    def _cmd_blast_radius(self, node: str) -> None:
        kg = self.kg
        candidates = [node, f"dataset:{node}", f"transform:{node}"]
        start = None
        for cid in candidates:
            if kg.has_node(cid):
                start = cid
                break
        if not start:
            console.print(f"[yellow]Node '{node}' not found.[/]")
            return

        downstream = kg.bfs_downstream(start)
        console.print(f"[bold]Blast radius for '{node}': {len(downstream)} downstream node(s)[/]")
        for nid in sorted(downstream):
            evidence = kg.get_evidence(nid)
            path = evidence.get("path") or nid
            ls = evidence.get("line_start")
            le = evidence.get("line_end")
            loc = f"{path}:{ls}-{le}" if ls and le else path
            console.print(f"- {nid}  [dim]({loc})[/]")

    def _cmd_explain_module(self, path: str) -> None:
        """Retrieve purpose statement + optional LLM elaboration."""
        # Try to find module node by exact or path match.
        nid = None
        for candidate, data in self.kg.graph.nodes(data=True):
            if data.get("node_type") != "ModuleNode":
                continue
            if candidate == path or data.get("path") == path:
                nid = candidate
                break
        if not nid:
            console.print(f"[yellow]Module '{path}' not found.[/]")
            return

        data = self.kg.get_node(nid) or {}
        purpose = data.get("purpose_statement") or "_No purpose statement recorded (run Semanticist)._"
        console.print(f"[bold]Module:[/] {nid}")
        console.print(f"[bold]Purpose:[/] {purpose}")

        api_key = os.getenv(OPENROUTER_API_KEY_ENV)
        if not api_key:
            return  # Don't attempt online elaboration without a key.

        context = (
            f"Module id: {nid}\n"
            f"Path: {data.get('path', nid)}\n"
            f"Purpose: {purpose}\n"
        )
        doc = data.get("docstring") or ""
        if doc:
            context += f"\nExisting docstring:\n{doc}\n"

        try:
            model_name = os.getenv(OPENROUTER_EXPLAIN_MODEL_ENV, "openrouter/openai/gpt-4o-mini")
            resp = completion(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You explain code modules to new engineers."},
                    {"role": "user", "content": f"Explain this module in 3–5 sentences:\n\n{context}"},
                ],
                max_tokens=256,
            )
            explanation = resp["choices"][0]["message"]["content"].strip()
            console.print("\n[bold]LLM Explanation:[/]")
            console.print(explanation)
        except Exception as exc:
            logger.warning("Navigator explain_module LLM call failed: %s", exc)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _load_lineage_graph(self) -> KnowledgeGraph:
        if self.lineage_graph_path.exists():
            return KnowledgeGraph.deserialize(self.lineage_graph_path)
        return self.kg

    def _route_question(self, question: str) -> None:
        """Very simple router for natural-language questions."""
        q = question.lower()
        # Lineage-style questions.
        if any(word in q for word in ["upstream", "downstream", "feeds", "source of", "produces"]):
            # Heuristic: try to extract a token that looks like a dataset name.
            tokens = q.replace("?", " ").split()
            if tokens:
                candidate = tokens[-1]
                self._cmd_trace_lineage(candidate, "downstream")
                return

        # Blast radius-style questions.
        if "blast radius" in q or "what breaks if" in q:
            tokens = q.replace("?", " ").split()
            if tokens:
                candidate = tokens[-1]
                self._cmd_blast_radius(candidate)
                return

        # Otherwise, treat as concept search over modules.
        self._cmd_find_implementation(question)

