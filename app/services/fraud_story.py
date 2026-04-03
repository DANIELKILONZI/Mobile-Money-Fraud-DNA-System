"""Fraud Story Mode — turns raw risk signals into a human-readable narrative."""

from typing import Optional

from app.core.storage import Store
from app.graph.builder import GraphManager


class FraudStoryBuilder:
    """Builds a FraudStory dict when suspicious patterns are present."""

    def __init__(self, store: Store, graph_manager: GraphManager) -> None:
        self.store = store
        self.gm = graph_manager

    def build(self, user_id: str, reasons: list[str], risk_score: float) -> Optional[dict]:
        """Return a fraud_story dict or None if the entity looks clean."""
        chains = self._build_chains(user_id)
        device_link = self._build_device_link(user_id)

        # Only build a story when there's something concrete to say
        has_patterns = bool(chains or device_link or any(
            kw in " ".join(reasons).lower()
            for kw in ("structuring", "spike", "circular", "new account")
        ))
        if not has_patterns and risk_score < 0.4:
            return None

        pattern = self._classify_pattern(reasons, chains, device_link)
        summary = self._build_summary(user_id, reasons, chains, device_link, pattern)

        if not summary:
            return None

        return {
            "summary": summary,
            "chain": chains,
            "device_link": device_link,
            "pattern": pattern,
        }

    # ── private helpers ─────────────────────────────────────────────────────

    def _build_chains(self, user_id: str) -> list[str]:
        """Find money-flow cycles and render them as 'A → B → C → A'."""
        raw_cycles = self.gm.get_cycles_for_node(user_id)
        rendered = []
        for cycle in raw_cycles:
            # Close the loop: append the first node again
            nodes = cycle + [cycle[0]]
            rendered.append(" → ".join(nodes))
        return rendered

    def _build_device_link(self, user_id: str) -> Optional[str]:
        """Describe shared-device exposure, if any."""
        sent = self.store.get_sent_transactions(user_id)
        devices = {tx.device_id for tx in sent if tx.device_id}
        for device_id in devices:
            count = self.store.get_device_user_count(device_id)
            if count > 1:
                return f"Shared device ({device_id}) used by {count} users"
        return None

    def _classify_pattern(
        self,
        reasons: list[str],
        chains: list[str],
        device_link: Optional[str],
    ) -> str:
        """Combine detected signals into a short pattern label."""
        parts = []
        reasons_lower = " ".join(reasons).lower()

        if chains:
            parts.append("Circular fund movement")
        if device_link:
            parts.append("Device sharing")
        if "structuring" in reasons_lower or "small transfer" in reasons_lower:
            parts.append("Structuring")
        if "spike" in reasons_lower or "velocity" in reasons_lower:
            parts.append("Velocity anomaly")
        if "new account" in reasons_lower:
            parts.append("New-account abuse")

        return " + ".join(parts) if parts else "Anomalous behaviour"

    def _build_summary(
        self,
        user_id: str,
        reasons: list[str],
        chains: list[str],
        device_link: Optional[str],
        pattern: str,
    ) -> str:
        """Generate a one-sentence human-readable summary."""
        parts = []

        if chains:
            # Count unique nodes across all cycles (excluding the anchor user)
            all_nodes: set[str] = set()
            for cycle_str in chains:
                nodes = [n.strip() for n in cycle_str.split("→")]
                all_nodes.update(nodes)
            all_nodes.discard(user_id)
            ring_size = len(all_nodes) + 1  # +1 for user_id itself
            parts.append(
                f"User is part of a suspected fraud ring involving {ring_size} accounts"
            )

        if device_link:
            # Extract count from the message
            parts.append(device_link)

        reasons_lower = " ".join(reasons).lower()
        if "structuring" in reasons_lower:
            parts.append("exhibits structuring behavior (high-frequency small transfers)")
        if "spike" in reasons_lower or "velocity" in reasons_lower:
            parts.append("shows a sudden transaction volume spike")
        if "new account" in reasons_lower:
            parts.append("is a new account transacting unusually high amounts")

        if not parts:
            return ""

        # Join with '; ' for a single sentence
        summary = "; ".join(parts)
        return summary[0].upper() + summary[1:] + "."
