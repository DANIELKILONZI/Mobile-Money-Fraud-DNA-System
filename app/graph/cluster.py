"""Suspicious Cluster Exporter — returns a color-annotated subgraph around a node."""

from typing import Any, Dict, Optional

import networkx as nx

from app.graph.builder import GraphManager


_RISK_COLOR = {
    "HIGH": "red",
    "MEDIUM": "orange",
    "LOW": "green",
    "UNKNOWN": "grey",
}


class ClusterExporter:
    """Export a BFS neighbourhood around a node, annotated with risk levels."""

    def __init__(self, graph_manager: GraphManager) -> None:
        self.gm = graph_manager

    def get_suspicious_cluster(
        self,
        center_id: str,
        risk_scorer,   # callable: (node_id, node_type) -> dict with risk_level/risk_score
        depth: int = 2,
    ) -> Optional[dict]:
        """
        Return a JSON-serializable subgraph centered on *center_id*.

        Each node carries:
          id, type, risk_level, risk_score, color

        Each edge carries:
          source, target, amount, tx_count, edge_type
        """
        g = self.gm.graph
        if not g.has_node(center_id):
            return None

        # BFS to collect neighbourhood up to *depth* hops
        neighbours: set[str] = {center_id}
        frontier = {center_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for n in frontier:
                next_frontier.update(g.successors(n))
                next_frontier.update(g.predecessors(n))
            next_frontier -= neighbours
            neighbours.update(next_frontier)
            frontier = next_frontier

        subgraph = g.subgraph(neighbours)

        # Build node list with risk annotation
        nodes = []
        for node_id in subgraph.nodes:
            node_type = g.nodes[node_id].get("node_type", "unknown")
            scored = risk_scorer(node_id, node_type)
            risk_level = scored.get("risk_level", "UNKNOWN")
            risk_score = scored.get("risk_score", 0.0)
            nodes.append({
                "id": node_id,
                "type": node_type,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "color": _RISK_COLOR.get(risk_level, "grey"),
                "is_center": node_id == center_id,
            })

        # Build edge list
        edges = []
        for src, tgt, data in subgraph.edges(data=True):
            # Skip device edges to keep transaction flows readable
            if data.get("edge_type") == "used_device":
                continue
            edges.append({
                "source": src,
                "target": tgt,
                "amount": data.get("amount"),
                "total_amount": data.get("total_amount"),
                "tx_count": data.get("tx_count", 1),
            })

        # Cluster-level risk: maximum risk_score in the subgraph
        cluster_risk = max((n["risk_score"] for n in nodes), default=0.0)

        return {
            "center_node": center_id,
            "depth": depth,
            "cluster_risk": round(cluster_risk, 4),
            "nodes": nodes,
            "edges": edges,
        }
