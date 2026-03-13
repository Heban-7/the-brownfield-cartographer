"""Semanticist Agent — LLM-powered purpose & domain analysis.

This module is designed to work with OpenRouter via `litellm`, but it will
gracefully NO-OP if no API key is configured. That keeps the core system
usable without network access and lets you wire in keys when you are ready.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from litellm import completion, embedding

from src.graph.knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)


OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"


@dataclass
class ContextWindowBudget:
    """Rudimentary token / cost budget tracker.

    We approximate tokens by character length / 4, which is usually fine
    for budget discipline at this level of fidelity.
    """

    max_tokens: int = 80_000
    used_tokens: int = 0

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def consume(self, *texts: str) -> bool:
        est = sum(self.estimate_tokens(t) for t in texts)
        if self.used_tokens + est > self.max_tokens:
            return False
        self.used_tokens += est
        return True


class SemanticistAgent:
    """Adds semantic understanding on top of static analysis results.

    Responsibilities:
      - Generate purpose statements for modules
      - Detect documentation drift vs. existing docstrings
      - Cluster modules into rough domains
      - Synthesize Day-One answers (stubbed here, but wired)
    """

    def __init__(
        self,
        repo_path: str | Path,
        module_graph: Optional[KnowledgeGraph],
        lineage_graph: Optional[KnowledgeGraph],
        bulk_model: str = "openrouter/google/gemini-flash-1.5",
        synth_model: str = "openrouter/openai/gpt-4o-mini",
        max_tokens: int = 80_000,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.module_graph = module_graph
        self.lineage_graph = lineage_graph
        self.bulk_model = bulk_model
        self.synth_model = synth_model
        self.budget = ContextWindowBudget(max_tokens=max_tokens)

        self.api_key = os.getenv(OPENROUTER_API_KEY_ENV)
        if not self.api_key:
            logger.warning(
                "Semanticist: %s not set; semantic analysis will be skipped.",
                OPENROUTER_API_KEY_ENV,
            )

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Run all semantic analysis steps.

        If no API key is configured, this becomes a NO-OP.
        """
        if not self.api_key:
            return
        if self.module_graph is None:
            logger.warning("Semanticist: no module graph available, skipping.")
            return

        logger.info("Semanticist: generating purpose statements …")
        self._generate_purpose_statements()

        logger.info("Semanticist: clustering modules into domains …")
        self._cluster_into_domains()

        logger.info("Semanticist: (optional) synthesizing Day-One answers …")
        # Day-One answers are written to CODEBASE.md / onboarding_brief
        # by the Archivist; here we only prepare structured context.
        self._prepare_day_one_context()

    # ------------------------------------------------------------------ #
    # Purpose statements
    # ------------------------------------------------------------------ #

    def _iter_module_nodes(self) -> Iterable[Tuple[str, Dict[str, Any]]]:
        for nid, data in self.module_graph.graph.nodes(data=True):
            if data.get("node_type") == "ModuleNode":
                yield nid, data

    def _generate_purpose_statements(self) -> None:
        for nid, data in self._iter_module_nodes():
            path = data.get("path") or nid
            language = data.get("language", "unknown")
            if language != "python":
                # For now, focus on Python modules; SQL/YAML can be added later.
                continue

            try:
                source_path = self.repo_path / path
                source_text = source_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.debug("Semanticist: cannot read %s: %s", path, exc)
                continue

            existing_doc = data.get("docstring", "")
            if not self.budget.consume(source_text, existing_doc):
                logger.info("Semanticist: budget exhausted, stopping purpose generation.")
                break

            prompt = self._build_purpose_prompt(path, source_text, existing_doc)
            try:
                resp = completion(
                    model=self.bulk_model,
                    messages=[
                        {"role": "system", "content": "You are a senior FDE summarizing code modules."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=256,
                )
                summary = resp["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                logger.warning("Semanticist: completion failed for %s: %s", path, exc)
                continue

            # Very simple drift heuristic: if docstring exists and differs significantly.
            drift_flag = bool(existing_doc and existing_doc.strip() and existing_doc.strip()[:80] not in summary)

            self.module_graph.graph.nodes[nid]["purpose_statement"] = summary
            if drift_flag:
                self.module_graph.graph.nodes[nid]["doc_drift"] = True

    @staticmethod
    def _build_purpose_prompt(module_path: str, code: str, docstring: str) -> str:
        return (
            f"You are analyzing module '{module_path}'.\n\n"
            "1. Read the code below.\n"
            "2. Ignore any comments and docstrings as *ground truth*; they may be stale.\n"
            "3. In 2–3 sentences, explain the *business purpose* of this module,\n"
            "   not low-level implementation details.\n"
            "4. If the existing top-level docstring meaningfully contradicts the implementation,\n"
            "   mention that there is 'documentation drift'.\n\n"
            f"Existing top-level docstring (may be stale):\n{docstring}\n\n"
            "Module code:\n"
            "```python\n"
            f"{code[:4000]}\n"
            "```"
        )

    # ------------------------------------------------------------------ #
    # Domain clustering (high level stub)
    # ------------------------------------------------------------------ #

    def _cluster_into_domains(self) -> None:
        """Embed purpose statements and assign coarse domains.

        To keep this light and dependency-free beyond litellm, we don't run
        k-means here; instead we:
          - embed each purpose statement
          - ask the LLM to bucket modules into 5–8 domain labels
        This is sufficient for a Day-One architectural view.
        """
        # Collect modules with purpose statements
        modules: List[Tuple[str, str]] = []
        for nid, data in self._iter_module_nodes():
            purpose = (data.get("purpose_statement") or "").strip()
            if purpose:
                modules.append((nid, purpose))

        if not modules:
            logger.info("Semanticist: no purpose statements available to cluster.")
            return

        if not self.budget.consume(*(p for _, p in modules)):
            logger.info("Semanticist: budget exhausted before clustering.")
            return

        # Ask model to cluster textually (simpler than embeddings + k-means).
        items_json = json.dumps(
            [{"id": nid, "purpose": purpose} for nid, purpose in modules],
            ensure_ascii=False,
        )
        prompt = (
            "You are clustering code modules into high-level business domains.\n"
            "Given a list of modules with purpose statements, group them into 5–8\n"
            "domain labels (e.g., 'ingestion', 'transformation', 'serving', 'monitoring').\n\n"
            "Return STRICT JSON as a list of objects: {\"id\": <module_id>, \"domain\": <label>}.\n\n"
            f"Modules:\n{items_json}"
        )

        try:
            resp = completion(
                model=self.bulk_model,
                messages=[
                    {"role": "system", "content": "You produce strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=512,
            )
            content = resp["choices"][0]["message"]["content"].strip()
            mapping = json.loads(content)
        except Exception as exc:
            logger.warning("Semanticist: domain clustering failed: %s", exc)
            return

        if not isinstance(mapping, list):
            logger.warning("Semanticist: clustering response not a list, skipping.")
            return

        for item in mapping:
            try:
                mid = item["id"]
                dom = item["domain"]
            except Exception:
                continue
            if mid in self.module_graph.graph.nodes:
                self.module_graph.graph.nodes[mid]["domain_cluster"] = dom

    # ------------------------------------------------------------------ #
    # Day-One context preparation (synthesis happens in Archivist)
    # ------------------------------------------------------------------ #

    def _prepare_day_one_context(self) -> None:
        """Attach a compact snapshot of key facts to the module graph.

        The Archivist will later feed this into an LLM to answer the
        Five Day-One questions with citations.
        """
        if not self.lineage_graph:
            return

        summary = {
            "repo_path": str(self.repo_path),
            "module_graph_nodes": self.module_graph.node_count if self.module_graph else 0,
            "lineage_graph_nodes": self.lineage_graph.node_count,
        }
        # Store under graph-level attribute for Archivist to read.
        self.lineage_graph.graph.graph["semantic_summary"] = summary

