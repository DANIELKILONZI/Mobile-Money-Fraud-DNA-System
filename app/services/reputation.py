"""Entity Reputation Score — long-term risk tracking with exponential decay."""

from datetime import datetime, timezone
from typing import Dict, List, Tuple


# Exponential-weighted moving-average decay factor (0-1).
# 0.85 means recent scores count for ~85% of the new average.
EWMA_ALPHA = 0.3
# Maximum number of historical scores to retain per entity
MAX_HISTORY = 50


class ReputationManager:
    """Tracks a rolling long-term risk score per entity."""

    def __init__(self) -> None:
        # entity_id -> list of (iso_timestamp, score)
        self._history: Dict[str, List[Tuple[str, float]]] = {}
        # entity_id -> current EWMA long-term score
        self._long_term: Dict[str, float] = {}

    def update(self, entity_id: str, score: float) -> None:
        """Record a new risk score observation and update the EWMA."""
        now = datetime.now(timezone.utc).isoformat()

        if entity_id not in self._history:
            self._history[entity_id] = []
            self._long_term[entity_id] = score
        else:
            prev = self._long_term[entity_id]
            self._long_term[entity_id] = round(
                EWMA_ALPHA * score + (1 - EWMA_ALPHA) * prev, 4
            )

        history = self._history[entity_id]
        history.append((now, score))
        if len(history) > MAX_HISTORY:
            self._history[entity_id] = history[-MAX_HISTORY:]

    def get_long_term_score(self, entity_id: str) -> float:
        return self._long_term.get(entity_id, 0.0)

    def get_history(self, entity_id: str) -> List[Tuple[str, float]]:
        return list(self._history.get(entity_id, []))

    def get_reputation_info(self, entity_id: str) -> dict:
        """Return a concise reputation snapshot."""
        history = self._history.get(entity_id, [])
        long_term = self._long_term.get(entity_id, 0.0)

        trend = "STABLE"
        if len(history) >= 3:
            recent_avg = sum(s for _, s in history[-3:]) / 3
            older_avg = sum(s for _, s in history[:-3]) / max(len(history) - 3, 1)
            delta = recent_avg - older_avg
            if delta > 0.05:
                trend = "RISING"
            elif delta < -0.05:
                trend = "FALLING"

        return {
            "long_term_score": long_term,
            "score_count": len(history),
            "trend": trend,
        }


# Application-wide singleton
reputation_manager = ReputationManager()
