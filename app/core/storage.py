from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.models.entities import User, Merchant, Device, Transaction


def _ensure_aware(dt: datetime) -> datetime:
    """Make a datetime timezone-aware (UTC) if it is naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class Store:
    """In-memory storage for all entities and transactions."""

    def __init__(self) -> None:
        self.users: Dict[str, User] = {}
        self.merchants: Dict[str, Merchant] = {}
        self.devices: Dict[str, Device] = {}
        self.transactions: Dict[str, Transaction] = {}
        # Maps device_id -> set of user_ids that used it
        self.device_users: Dict[str, set] = {}

    def get_or_create_user(self, user_id: str) -> User:
        if user_id not in self.users:
            self.users[user_id] = User(user_id=user_id)
        return self.users[user_id]

    def get_or_create_merchant(self, merchant_id: str, category: str = "general") -> Merchant:
        if merchant_id not in self.merchants:
            self.merchants[merchant_id] = Merchant(merchant_id=merchant_id, category=category)
        return self.merchants[merchant_id]

    def get_or_create_device(self, device_id: str) -> Device:
        if device_id not in self.devices:
            self.devices[device_id] = Device(device_id=device_id)
        return self.devices[device_id]

    def add_transaction(self, tx: Transaction) -> None:
        self.transactions[tx.tx_id] = tx
        if tx.device_id:
            if tx.device_id not in self.device_users:
                self.device_users[tx.device_id] = set()
            self.device_users[tx.device_id].add(tx.sender_id)

    def get_user_transactions(self, user_id: str) -> List[Transaction]:
        return [
            tx for tx in self.transactions.values()
            if tx.sender_id == user_id or tx.receiver_id == user_id
        ]

    def get_sent_transactions(self, user_id: str) -> List[Transaction]:
        return [tx for tx in self.transactions.values() if tx.sender_id == user_id]

    def get_received_transactions(self, entity_id: str) -> List[Transaction]:
        return [tx for tx in self.transactions.values() if tx.receiver_id == entity_id]

    def get_transactions_since(self, user_id: str, since: datetime) -> List[Transaction]:
        since = _ensure_aware(since)
        return [
            tx for tx in self.get_sent_transactions(user_id)
            if _ensure_aware(tx.timestamp) >= since
        ]

    def get_device_user_count(self, device_id: str) -> int:
        return len(self.device_users.get(device_id, set()))


# Application-wide singleton store
store = Store()
