"""Semantic index backed by Chroma for Navigator / Semanticist.

This module provides a tiny wrapper around a persistent ChromaDB collection
for module-level semantic search.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import chromadb

logger = logging.getLogger(__name__)


class SemanticIndex:
    """Persistent vector index for modules."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.base_dir))
        self.collection = self.client.get_or_create_collection("modules")

    def clear(self) -> None:
        self.client.delete_collection("modules")
        self.collection = self.client.get_or_create_collection("modules")

    def upsert_modules(
        self,
        items: List[Tuple[str, List[float], Dict[str, Any]]],
    ) -> None:
        """Upsert module vectors.

        items: list of (id, embedding_vector, metadata)
        """
        if not items:
            return
        ids = [i[0] for i in items]
        embeddings = [i[1] for i in items]
        metadatas = [i[2] for i in items]
        self.collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def query(self, text_embedding: List[float], k: int = 10) -> List[Dict[str, Any]]:
        if not text_embedding:
            return []
        res = self.collection.query(
            query_embeddings=[text_embedding],
            n_results=k,
        )
        results: List[Dict[str, Any]] = []
        for i in range(len(res.get("ids", [[]])[0])):
            results.append(
                {
                    "id": res["ids"][0][i],
                    "distance": res["distances"][0][i] if res.get("distances") else None,
                    "metadata": res["metadatas"][0][i],
                }
            )
        return results

