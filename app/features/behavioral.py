from datetime import datetime, timedelta, timezone
from typing import List
import statistics

from app.models.entities import Transaction
from app.core.storage import Store, _ensure_aware


class BehavioralFeatures:
    """Compute behavioral features for a user or merchant from transaction history."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def compute(self, entity_id: str) -> dict:
        now = datetime.now(timezone.utc)
        sent = self.store.get_sent_transactions(entity_id)

        freq_1h = self._count_since(sent, now - timedelta(hours=1))
        freq_24h = self._count_since(sent, now - timedelta(hours=24))
        freq_7d = self._count_since(sent, now - timedelta(days=7))

        amounts = [tx.amount for tx in sent]
        avg_amount = statistics.mean(amounts) if amounts else 0.0
        stdev_amount = statistics.stdev(amounts) if len(amounts) > 1 else 0.0

        amount_deviation_score = self._amount_deviation_score(amounts)
        burst_score = self._burst_score(sent, now)
        time_anomaly_score = self._time_anomaly_score(sent)

        # Account age in hours
        user = self.store.users.get(entity_id)
        account_age_hours = None
        if user:
            account_age_hours = (_ensure_aware(now) - _ensure_aware(user.created_at)).total_seconds() / 3600

        return {
            "freq_1h": freq_1h,
            "freq_24h": freq_24h,
            "freq_7d": freq_7d,
            "avg_amount": round(avg_amount, 2),
            "stdev_amount": round(stdev_amount, 2),
            "amount_deviation_score": round(amount_deviation_score, 4),
            "burst_score": round(burst_score, 4),
            "time_anomaly_score": round(time_anomaly_score, 4),
            "total_sent_transactions": len(sent),
            "account_age_hours": round(account_age_hours, 2) if account_age_hours is not None else None,
        }

    def _count_since(self, transactions: List[Transaction], since: datetime) -> int:
        since = _ensure_aware(since)
        return sum(1 for tx in transactions if _ensure_aware(tx.timestamp) >= since)

    def _amount_deviation_score(self, amounts: List[float]) -> float:
        """Score based on how much recent amount deviates from historical average."""
        if len(amounts) < 2:
            return 0.0
        mean = statistics.mean(amounts)
        stdev = statistics.stdev(amounts)
        if stdev == 0:
            return 0.0
        last = amounts[-1]
        z = abs(last - mean) / stdev
        # Normalize: z-score > 3 is anomalous
        return min(z / 3.0, 1.0)

    def _burst_score(self, transactions: List[Transaction], now: datetime) -> float:
        """Detect rapid burst of transactions in a short window."""
        window = timedelta(minutes=10)
        recent = [tx for tx in transactions if _ensure_aware(tx.timestamp) >= _ensure_aware(now - window)]
        count = len(recent)
        # >5 transactions in 10 minutes is highly suspicious
        if count == 0:
            return 0.0
        return min(count / 5.0, 1.0)

    def _time_anomaly_score(self, transactions: List[Transaction]) -> float:
        """Flag transactions that occur between midnight and 5am local time."""
        if not transactions:
            return 0.0
        night_count = sum(1 for tx in transactions if 0 <= tx.timestamp.hour < 5)
        return min(night_count / max(len(transactions), 1), 1.0)
