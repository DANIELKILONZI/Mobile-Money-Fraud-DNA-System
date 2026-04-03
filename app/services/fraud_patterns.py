from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from app.core.storage import Store, _ensure_aware
from app.graph.builder import GraphManager
from app.models.entities import Transaction


DEVICE_REUSE_THRESHOLD = 5          # users sharing same device
SPIKE_MULTIPLIER = 3.0              # 3x baseline triggers spike alert
STRUCTURING_MAX_AMOUNT = 1000.0     # small transfer threshold
STRUCTURING_MIN_COUNT = 5           # minimum count in window
STRUCTURING_WINDOW_MINUTES = 60
NEW_ACCOUNT_HOURS = 24
NEW_ACCOUNT_HIGH_VALUE = 50_000.0   # threshold for new account high-value


class FraudPatternDetector:
    """Rule-based fraud pattern detector."""

    def __init__(self, store: Store, graph_manager: GraphManager) -> None:
        self.store = store
        self.gm = graph_manager

    def detect_for_user(self, user_id: str) -> List[str]:
        flags: List[str] = []
        flags.extend(self._device_reuse(user_id))
        flags.extend(self._volume_spike(user_id))
        flags.extend(self._circular_flow(user_id))
        flags.extend(self._structuring(user_id))
        flags.extend(self._new_account_high_value(user_id))
        return flags

    def detect_for_transaction(self, tx: Transaction) -> List[str]:
        flags: List[str] = []
        if tx.device_id:
            user_count = self.store.get_device_user_count(tx.device_id)
            if user_count > DEVICE_REUSE_THRESHOLD:
                flags.append(
                    f"Device {tx.device_id} shared across {user_count} users (threshold: {DEVICE_REUSE_THRESHOLD})"
                )
        flags.extend(self._new_account_high_value_tx(tx))
        return flags

    # --- private helpers ---

    def _device_reuse(self, user_id: str) -> List[str]:
        flags = []
        user_txs = self.store.get_sent_transactions(user_id)
        seen_devices = {tx.device_id for tx in user_txs if tx.device_id}
        for device_id in seen_devices:
            user_count = self.store.get_device_user_count(device_id)
            if user_count > DEVICE_REUSE_THRESHOLD:
                flags.append(
                    f"Device {device_id} shared across {user_count} users"
                )
        return flags

    def _volume_spike(self, user_id: str) -> List[str]:
        now = datetime.now(timezone.utc)
        recent_1h = self.store.get_transactions_since(user_id, now - timedelta(hours=1))
        recent_baseline = self.store.get_transactions_since(user_id, now - timedelta(hours=25))
        # Baseline = transactions in hours 2-25 / 24 (hourly rate)
        baseline_count = max(len(recent_baseline) - len(recent_1h), 0) / 24
        if baseline_count > 0 and len(recent_1h) > SPIKE_MULTIPLIER * baseline_count:
            return [
                f"Transaction volume spike: {len(recent_1h)} in last hour vs baseline {baseline_count:.1f}/hr"
            ]
        return []

    def _circular_flow(self, user_id: str) -> List[str]:
        if self.gm.detect_cycles(user_id):
            return ["Circular money flow detected involving this entity"]
        return []

    def _structuring(self, user_id: str) -> List[str]:
        now = datetime.now(timezone.utc)
        window_txs = self.store.get_transactions_since(
            user_id, now - timedelta(minutes=STRUCTURING_WINDOW_MINUTES)
        )
        small = [tx for tx in window_txs if tx.amount < STRUCTURING_MAX_AMOUNT]
        if len(small) >= STRUCTURING_MIN_COUNT:
            return [
                f"Structuring behavior: {len(small)} small transfers (<{STRUCTURING_MAX_AMOUNT}) "
                f"in last {STRUCTURING_WINDOW_MINUTES} minutes"
            ]
        return []

    def _new_account_high_value(self, user_id: str) -> List[str]:
        user = self.store.users.get(user_id)
        if not user:
            return []
        age_hours = (datetime.now(timezone.utc) - _ensure_aware(user.created_at)).total_seconds() / 3600
        if age_hours > NEW_ACCOUNT_HOURS:
            return []
        sent = self.store.get_sent_transactions(user_id)
        high_value = [tx for tx in sent if tx.amount >= NEW_ACCOUNT_HIGH_VALUE]
        if high_value:
            return [
                f"New account (age: {age_hours:.1f}h) sent high-value transaction "
                f"(amount: {high_value[0].amount})"
            ]
        return []

    def _new_account_high_value_tx(self, tx: Transaction) -> List[str]:
        user = self.store.users.get(tx.sender_id)
        if not user:
            return []
        age_hours = (datetime.now(timezone.utc) - _ensure_aware(user.created_at)).total_seconds() / 3600
        if age_hours <= NEW_ACCOUNT_HOURS and tx.amount >= NEW_ACCOUNT_HIGH_VALUE:
            return [
                f"New account (age: {age_hours:.1f}h) initiated high-value transaction "
                f"(amount: {tx.amount})"
            ]
        return []
