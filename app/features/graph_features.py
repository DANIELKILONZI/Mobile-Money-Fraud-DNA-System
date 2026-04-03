from app.graph.builder import GraphManager


class GraphFeatures:
    """Extract graph-based features for a node."""

    def __init__(self, graph_manager: GraphManager) -> None:
        self.gm = graph_manager

    def compute(self, node_id: str) -> dict:
        return {
            "degree_centrality": round(self.gm.degree_centrality(node_id), 4),
            "in_degree": self.gm.in_degree(node_id),
            "out_degree": self.gm.out_degree(node_id),
            "clustering_coefficient": round(self.gm.clustering_coefficient(node_id), 4),
            "unique_counterparties": self.gm.unique_counterparties(node_id),
            "shared_device_count": self.gm.shared_device_count(node_id),
            "in_cycle": self.gm.detect_cycles(node_id),
        }
