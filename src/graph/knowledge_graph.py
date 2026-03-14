"""NetworkX-backed knowledge graph with Pydantic model integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import networkx as nx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Thin wrapper around a NetworkX DiGraph storing typed nodes and edges."""

    def __init__(self):
        self.graph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node_id: str, node: BaseModel, node_type: str = "") -> None:
        self.graph.add_node(
            node_id,
            node_type=node_type or type(node).__name__,
            **node.model_dump(mode="json"),
        )

    def get_node(self, node_id: str) -> Optional[dict]:
        if node_id in self.graph:
            return dict(self.graph.nodes[node_id])
        return None

    def has_node(self, node_id: str) -> bool:
        return node_id in self.graph

    def nodes_by_type(self, node_type: str) -> list[tuple[str, dict]]:
        return [
            (nid, data)
            for nid, data in self.graph.nodes(data=True)
            if data.get("node_type") == node_type
        ]

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(
        self,
        source: str,
        target: str,
        edge: Optional[BaseModel] = None,
        edge_type: str = "",
        **extra: Any,
    ) -> None:
        data: dict[str, Any] = {"edge_type": edge_type}
        if edge is not None:
            data.update(edge.model_dump(mode="json"))
            if not edge_type:
                data["edge_type"] = type(edge).__name__
        data.update(extra)
        self.graph.add_edge(source, target, **data)

    def get_edges(self, source: str, target: str) -> list[dict]:
        if self.graph.has_edge(source, target):
            return [dict(self.graph.edges[source, target])]
        return []

    def edges_by_type(self, edge_type: str) -> list[tuple[str, str, dict]]:
        return [
            (u, v, d)
            for u, v, d in self.graph.edges(data=True)
            if d.get("edge_type") == edge_type
        ]

    # ------------------------------------------------------------------
    # Graph analysis helpers
    # ------------------------------------------------------------------

    def predecessors(self, node_id: str) -> list[str]:
        if node_id not in self.graph:
            return []
        return list(self.graph.predecessors(node_id))

    def successors(self, node_id: str) -> list[str]:
        if node_id not in self.graph:
            return []
        return list(self.graph.successors(node_id))

    def pagerank(self, **kwargs) -> dict[str, float]:
        if self.graph.number_of_nodes() == 0:
            return {}
        return nx.pagerank(self.graph, **kwargs)

    def strongly_connected_components(self) -> list[set[str]]:
        return [
            comp
            for comp in nx.strongly_connected_components(self.graph)
            if len(comp) > 1
        ]

    def bfs_downstream(self, start: str) -> set[str]:
        """BFS from *start* following outgoing edges; returns all reachable nodes."""
        if start not in self.graph:
            return set()
        return set(nx.descendants(self.graph, start))

    def bfs_upstream(self, start: str) -> set[str]:
        """BFS from *start* following incoming edges; returns all ancestors."""
        if start not in self.graph:
            return set()
        return set(nx.ancestors(self.graph, start))

    def subgraph(self, nodes: set[str]) -> "KnowledgeGraph":
        kg = KnowledgeGraph()
        kg.graph = self.graph.subgraph(nodes).copy()
        return kg

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def serialize(self, path: str | Path) -> None:
        """Write the graph to a JSON file using node-link format."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Graph serialized to %s (%d nodes, %d edges)", path, self.node_count, self.edge_count)

    @classmethod
    def deserialize(cls, path: str | Path) -> "KnowledgeGraph":
        """Load a graph from a node-link JSON file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        kg = cls()
        kg.graph = nx.node_link_graph(data)
        logger.info("Graph loaded from %s (%d nodes, %d edges)", path, kg.node_count, kg.edge_count)
        return kg

    def merge(self, other: "KnowledgeGraph") -> None:
        """Merge another graph into this one, updating existing nodes."""
        self.graph = nx.compose(self.graph, other.graph)

    def summary(self) -> dict[str, Any]:
        """Return a quick summary of graph contents."""
        node_types: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            nt = data.get("node_type", "unknown")
            node_types[nt] = node_types.get(nt, 0) + 1
        edge_types: dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            et = data.get("edge_type", "unknown")
            edge_types[et] = edge_types.get(et, 0) + 1
        return {
            "total_nodes": self.node_count,
            "total_edges": self.edge_count,
            "node_types": node_types,
            "edge_types": edge_types,
            "strongly_connected_components": len(self.strongly_connected_components()),
        }

    # ------------------------------------------------------------------
    # Evidence helpers
    # ------------------------------------------------------------------

    def get_evidence(self, node_id: str) -> dict[str, Any]:
        """Return basic evidence for a node: file path and line range if available."""
        data = self.get_node(node_id) or {}
        node_type = data.get("node_type")

        if node_type == "ModuleNode":
            return {
                "path": data.get("path"),
                "line_start": data.get("line_start", 1),
                "line_end": data.get("line_end", data.get("lines_of_code", 0)),
            }
        if node_type == "FunctionNode":
            return {
                "path": data.get("parent_module"),
                "line_start": data.get("line_start"),
                "line_end": data.get("line_end"),
            }
        if node_type == "DatasetNode":
            return {
                "path": data.get("source_file"),
                "line_start": data.get("line_number"),
                "line_end": data.get("line_number"),
            }
        if node_type == "TransformationNode":
            return {
                "path": data.get("source_file"),
                "line_start": data.get("line_start"),
                "line_end": data.get("line_end"),
            }
        return {}

    def get_edge_evidence(self, source: str, target: str) -> dict[str, Any]:
        """Return evidence for an edge (usually data lineage edges)."""
        if not self.graph.has_edge(source, target):
            return {}
        data = dict(self.graph.edges[source, target])
        return {
            "edge_type": data.get("edge_type"),
            "source_file": data.get("source_file"),
            "line_range": data.get("line_range"),
        }
