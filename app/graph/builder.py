import itertools
from typing import Optional
import networkx as nx
from app.models.entities import Transaction


class GraphManager:
    """Manages a directed multigraph of users, merchants, and devices."""

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    def add_transaction(self, tx: Transaction, receiver_type: str = "user") -> None:
        # Ensure nodes exist with type labels
        if not self.graph.has_node(tx.sender_id):
            self.graph.add_node(tx.sender_id, node_type="user")

        receiver_type_label = receiver_type
        if not self.graph.has_node(tx.receiver_id):
            self.graph.add_node(tx.receiver_id, node_type=receiver_type_label)

        if tx.device_id and not self.graph.has_node(tx.device_id):
            self.graph.add_node(tx.device_id, node_type="device")

        # Add transaction edge
        if self.graph.has_edge(tx.sender_id, tx.receiver_id):
            # Aggregate: store last amount and timestamp, bump count
            data = self.graph[tx.sender_id][tx.receiver_id]
            data["tx_count"] = data.get("tx_count", 1) + 1
            data["total_amount"] = data.get("total_amount", data.get("amount", 0)) + tx.amount
            data["amount"] = tx.amount
            data["timestamp"] = tx.timestamp.isoformat()
        else:
            self.graph.add_edge(
                tx.sender_id,
                tx.receiver_id,
                amount=tx.amount,
                total_amount=tx.amount,
                tx_count=1,
                timestamp=tx.timestamp.isoformat(),
            )

        # Add device-user edge if device present
        if tx.device_id:
            if not self.graph.has_edge(tx.sender_id, tx.device_id):
                self.graph.add_edge(tx.sender_id, tx.device_id, edge_type="used_device")

    def get_node_type(self, node_id: str) -> Optional[str]:
        if self.graph.has_node(node_id):
            return self.graph.nodes[node_id].get("node_type")
        return None

    def degree_centrality(self, node_id: str) -> float:
        if not self.graph.has_node(node_id) or len(self.graph) <= 1:
            return 0.0
        centrality = nx.degree_centrality(self.graph)
        return centrality.get(node_id, 0.0)

    def in_degree(self, node_id: str) -> int:
        if not self.graph.has_node(node_id):
            return 0
        return self.graph.in_degree(node_id)

    def out_degree(self, node_id: str) -> int:
        if not self.graph.has_node(node_id):
            return 0
        return self.graph.out_degree(node_id)

    def clustering_coefficient(self, node_id: str) -> float:
        if not self.graph.has_node(node_id):
            return 0.0
        try:
            undirected = self.graph.to_undirected()
            return nx.clustering(undirected, node_id)
        except Exception:
            return 0.0

    def unique_counterparties(self, node_id: str) -> int:
        if not self.graph.has_node(node_id):
            return 0
        successors = set(self.graph.successors(node_id))
        predecessors = set(self.graph.predecessors(node_id))
        # Exclude device nodes
        counterparties = (successors | predecessors) - {node_id}
        counterparties = {
            n for n in counterparties
            if self.graph.nodes[n].get("node_type") != "device"
        }
        return len(counterparties)

    def shared_device_count(self, node_id: str) -> int:
        """Number of devices shared with other users."""
        shared = 0
        for neighbor in self.graph.successors(node_id):
            if self.graph.nodes[neighbor].get("node_type") == "device":
                # Count how many user nodes use this device
                users_on_device = [
                    n for n in self.graph.predecessors(neighbor)
                    if self.graph.nodes[n].get("node_type") == "user"
                ]
                if len(users_on_device) > 1:
                    shared += 1
        return shared

    def detect_cycles(self, node_id: str, max_length: int = 5) -> bool:
        """Detect if node is part of a money-flow cycle."""
        if not self.graph.has_node(node_id):
            return False
        try:
            cycles = (
                cycle
                for cycle in nx.simple_cycles(self.graph)
                if node_id in cycle and len(cycle) <= max_length
            )
            return next(cycles, None) is not None
        except Exception:
            return False

    def get_flagged_neighbors(self, node_id: str, flagged_nodes: set) -> int:
        """Count how many direct neighbors are flagged."""
        if not self.graph.has_node(node_id):
            return 0
        neighbors = set(self.graph.successors(node_id)) | set(self.graph.predecessors(node_id))
        return len(neighbors & flagged_nodes)

    def summary(self) -> dict:
        return {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
        }


# Application-wide singleton graph
graph_manager = GraphManager()
