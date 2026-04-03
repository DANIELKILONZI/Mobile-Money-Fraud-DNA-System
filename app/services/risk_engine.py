import statistics
from typing import List, Optional

from app.core.storage import Store
from app.graph.builder import GraphManager
from app.features.behavioral import BehavioralFeatures
from app.features.graph_features import GraphFeatures
from app.services.fraud_patterns import FraudPatternDetector
from app.services.fraud_story import FraudStoryBuilder
from app.services.reputation import reputation_manager
from app.models.entities import Transaction


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def _build_alert(risk_level: str, reasons: list[str]) -> Optional[dict]:
    """Map detected patterns to a structured alert object."""
    if risk_level == "LOW":
        return None
    severity = risk_level
    reasons_lower = " ".join(reasons).lower()

    if "circular" in reasons_lower or "cycle" in reasons_lower:
        alert_type = "FRAUD_RING_DETECTED"
    elif "structuring" in reasons_lower or "small transfer" in reasons_lower:
        alert_type = "STRUCTURING_DETECTED"
    elif "device" in reasons_lower:
        alert_type = "DEVICE_SHARING_DETECTED"
    elif "spike" in reasons_lower or "velocity" in reasons_lower:
        alert_type = "VELOCITY_SPIKE"
    elif "new account" in reasons_lower:
        alert_type = "NEW_ACCOUNT_HIGH_VALUE"
    else:
        alert_type = "SUSPICIOUS_ACTIVITY"

    return {"alert_type": alert_type, "severity": severity}


class RiskEngine:
    """Hybrid risk scoring engine combining behavioral and graph analytics."""

    def __init__(self, store: Store, graph_manager: GraphManager) -> None:
        self.store = store
        self.gm = graph_manager
        self.behavioral = BehavioralFeatures(store)
        self.graph_feat = GraphFeatures(graph_manager)
        self.pattern_detector = FraudPatternDetector(store, graph_manager)
        self.story_builder = FraudStoryBuilder(store, graph_manager)

    def score_user(self, user_id: str) -> dict:
        beh = self.behavioral.compute(user_id)
        grf = self.graph_feat.compute(user_id)
        reasons = self.pattern_detector.detect_for_user(user_id)

        velocity_anomaly = self._velocity_anomaly(beh)
        graph_anomaly = self._graph_anomaly(grf)
        device_reuse_score = self._device_reuse_score(user_id)
        amount_outlier_score = beh["amount_deviation_score"]

        risk_score = round(
            velocity_anomaly * 0.3
            + graph_anomaly * 0.4
            + device_reuse_score * 0.2
            + amount_outlier_score * 0.1,
            4,
        )
        risk_score = min(risk_score, 1.0)

        reasons.extend(self._explain(velocity_anomaly, graph_anomaly, device_reuse_score, amount_outlier_score))
        reasons = list(set(reasons))

        risk_level = _risk_level(risk_score)

        # Update and fetch reputation
        reputation_manager.update(user_id, risk_score)
        reputation = reputation_manager.get_reputation_info(user_id)

        # Build fraud story (only when risk warrants it)
        fraud_story = self.story_builder.build(user_id, reasons, risk_score)

        # Build alert
        alert = _build_alert(risk_level, reasons)

        return {
            "entity_id": user_id,
            "entity_type": "user",
            "risk_score": risk_score,
            "risk_level": risk_level,
            "reasons": reasons,
            "features": {**beh, **grf},
            "fraud_story": fraud_story,
            "alert": alert,
            "reputation": reputation,
        }

    def score_merchant(self, merchant_id: str) -> dict:
        beh = self.behavioral.compute(merchant_id)
        grf = self.graph_feat.compute(merchant_id)

        # Merchants are receivers; look at received transactions for anomaly
        received = self.store.get_received_transactions(merchant_id)
        recv_amounts = [tx.amount for tx in received]

        graph_anomaly = self._graph_anomaly(grf)
        velocity_anomaly = min(len(received) / 50.0, 1.0)  # scale to 50 transactions
        device_reuse_score = 0.0  # merchants don't use devices
        amount_outlier_score = beh["amount_deviation_score"]

        risk_score = round(
            velocity_anomaly * 0.3
            + graph_anomaly * 0.4
            + device_reuse_score * 0.2
            + amount_outlier_score * 0.1,
            4,
        )
        risk_score = min(risk_score, 1.0)

        reasons: List[str] = []
        if graph_anomaly > 0.7:
            reasons.append("High graph centrality - unusually many connections")
        if velocity_anomaly > 0.7:
            reasons.append("High incoming transaction volume")

        risk_level = _risk_level(risk_score)

        # Update and fetch reputation
        reputation_manager.update(merchant_id, risk_score)
        reputation = reputation_manager.get_reputation_info(merchant_id)

        alert = _build_alert(risk_level, reasons)

        return {
            "entity_id": merchant_id,
            "entity_type": "merchant",
            "risk_score": risk_score,
            "risk_level": risk_level,
            "reasons": reasons,
            "features": {**beh, **grf, "total_received": len(recv_amounts)},
            "fraud_story": None,
            "alert": alert,
            "reputation": reputation,
        }

    def score_transaction(self, tx_id: str) -> dict:
        tx = self.store.transactions.get(tx_id)
        if tx is None:
            return {
                "entity_id": tx_id,
                "entity_type": "transaction",
                "risk_score": 0.0,
                "risk_level": "LOW",
                "reasons": ["Transaction not found"],
                "features": {},
                "fraud_story": None,
                "alert": None,
                "reputation": None,
            }

        sender_risk = self.score_user(tx.sender_id)
        reasons = self.pattern_detector.detect_for_transaction(tx)

        # Transaction inherits sender risk + device check
        device_reuse_score = self._device_reuse_score_by_device(tx.device_id) if tx.device_id else 0.0

        # Amount outlier for sender
        sent = self.store.get_sent_transactions(tx.sender_id)
        amounts = [t.amount for t in sent]
        amount_outlier = self._amount_z_score(tx.amount, amounts)

        risk_score = round(
            sender_risk["risk_score"] * 0.5
            + device_reuse_score * 0.3
            + amount_outlier * 0.2,
            4,
        )
        risk_score = min(risk_score, 1.0)

        if amount_outlier > 0.7:
            reasons.append(f"Transaction amount {tx.amount} is an outlier for this sender")

        risk_level = _risk_level(risk_score)
        alert = _build_alert(risk_level, reasons)

        return {
            "entity_id": tx_id,
            "entity_type": "transaction",
            "risk_score": risk_score,
            "risk_level": risk_level,
            "reasons": list(set(reasons)),
            "features": {
                "sender_id": tx.sender_id,
                "receiver_id": tx.receiver_id,
                "amount": tx.amount,
                "timestamp": tx.timestamp.isoformat(),
                "device_id": tx.device_id,
                "sender_risk_score": sender_risk["risk_score"],
                "device_reuse_score": device_reuse_score,
                "amount_outlier_score": amount_outlier,
            },
            "fraud_story": sender_risk.get("fraud_story"),
            "alert": alert,
            "reputation": None,
        }

    # --- private helpers ---

    def _velocity_anomaly(self, beh: dict) -> float:
        """Higher transaction frequency → higher anomaly score."""
        # Scale: >20 in 1h is suspicious; >10 in 1h is moderate
        freq_score = min(beh["freq_1h"] / 20.0, 1.0)
        burst = beh["burst_score"]
        time_anomaly = beh["time_anomaly_score"]
        return min((freq_score * 0.5 + burst * 0.3 + time_anomaly * 0.2), 1.0)

    def _graph_anomaly(self, grf: dict) -> float:
        centrality = grf["degree_centrality"]
        in_cycle = 1.0 if grf["in_cycle"] else 0.0
        shared_devices = min(grf["shared_device_count"] / 3.0, 1.0)
        counterparties = min(grf["unique_counterparties"] / 20.0, 1.0)
        return min(
            centrality * 0.3
            + in_cycle * 0.4
            + shared_devices * 0.2
            + counterparties * 0.1,
            1.0,
        )

    def _device_reuse_score(self, user_id: str) -> float:
        sent = self.store.get_sent_transactions(user_id)
        devices = {tx.device_id for tx in sent if tx.device_id}
        max_users = 0
        for device_id in devices:
            count = self.store.get_device_user_count(device_id)
            max_users = max(max_users, count)
        # >5 users on a device → score 1.0
        return min(max_users / 5.0, 1.0)

    def _device_reuse_score_by_device(self, device_id: str) -> float:
        count = self.store.get_device_user_count(device_id)
        return min(count / 5.0, 1.0)

    def _amount_z_score(self, amount: float, history: list) -> float:
        if len(history) < 2:
            return 0.0
        mean = statistics.mean(history)
        stdev = statistics.stdev(history)
        if stdev == 0:
            return 0.0
        z = abs(amount - mean) / stdev
        return min(z / 3.0, 1.0)

    def _explain(
        self,
        velocity: float,
        graph: float,
        device: float,
        amount: float,
    ) -> List[str]:
        reasons = []
        if velocity > 0.6:
            reasons.append(f"High velocity anomaly score ({velocity:.2f})")
        if graph > 0.6:
            reasons.append(f"High graph anomaly score ({graph:.2f}) - suspicious network position")
        if device > 0.6:
            reasons.append(f"Device shared across many users (score: {device:.2f})")
        if amount > 0.6:
            reasons.append(f"Unusual transaction amount (deviation score: {amount:.2f})")
        return reasons
