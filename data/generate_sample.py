"""Synthetic dataset generator for testing the Mobile Money Behavioral Risk Intelligence API."""

import random
import uuid
from datetime import datetime, timedelta
import json

SEED = 42
random.seed(SEED)

# ── Config ────────────────────────────────────────────────────────────────────
NUM_USERS = 20
NUM_MERCHANTS = 5
NUM_DEVICES = 12
NUM_TRANSACTIONS = 80

USER_IDS = [f"+2547{random.randint(10000000, 99999999)}" for _ in range(NUM_USERS)]
MERCHANT_IDS = [f"MERCH_{i:03d}" for i in range(NUM_MERCHANTS)]
DEVICE_IDS = [f"DEV_{uuid.uuid4().hex[:8].upper()}" for _ in range(NUM_DEVICES)]
CATEGORIES = ["grocery", "airtime", "utility", "restaurant", "transport"]


def random_timestamp(days_back: int = 7) -> str:
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    dt = datetime.utcnow() - delta
    return dt.isoformat()


def generate_transactions() -> list[dict]:
    transactions = []

    # Normal transactions
    for i in range(NUM_TRANSACTIONS - 15):
        sender = random.choice(USER_IDS)
        if random.random() < 0.3:
            receiver = random.choice(MERCHANT_IDS)
            receiver_type = "merchant"
        else:
            receiver = random.choice([u for u in USER_IDS if u != sender])
            receiver_type = "user"

        transactions.append(
            {
                "tx_id": f"TX_{uuid.uuid4().hex[:10].upper()}",
                "sender_id": sender,
                "receiver_id": receiver,
                "receiver_type": receiver_type,
                "amount": round(random.uniform(50, 5000), 2),
                "timestamp": random_timestamp(),
                "device_id": random.choice(DEVICE_IDS),
                "location": random.choice(["Nairobi", "Mombasa", "Kisumu", "Nakuru", None]),
                "merchant_category": random.choice(CATEGORIES),
            }
        )

    # ── Fraud patterns ────────────────────────────────────────────────────────

    # 1. Device reuse across many users (6 users share the same device)
    shared_device = DEVICE_IDS[0]
    for user in USER_IDS[:6]:
        transactions.append(
            {
                "tx_id": f"TX_{uuid.uuid4().hex[:10].upper()}",
                "sender_id": user,
                "receiver_id": random.choice(MERCHANT_IDS),
                "receiver_type": "merchant",
                "amount": round(random.uniform(100, 500), 2),
                "timestamp": random_timestamp(1),
                "device_id": shared_device,
                "location": "Nairobi",
                "merchant_category": "airtime",
            }
        )

    # 2. Circular money flow: A → B → C → A
    u_a, u_b, u_c = USER_IDS[0], USER_IDS[1], USER_IDS[2]
    now_iso = datetime.utcnow().isoformat()
    for sender, receiver in [(u_a, u_b), (u_b, u_c), (u_c, u_a)]:
        transactions.append(
            {
                "tx_id": f"TX_{uuid.uuid4().hex[:10].upper()}",
                "sender_id": sender,
                "receiver_id": receiver,
                "receiver_type": "user",
                "amount": 10000.0,
                "timestamp": now_iso,
                "device_id": DEVICE_IDS[1],
                "location": "Nairobi",
                "merchant_category": "general",
            }
        )

    # 3. High-frequency small transfers (structuring)
    structuring_user = USER_IDS[5]
    for _ in range(6):
        transactions.append(
            {
                "tx_id": f"TX_{uuid.uuid4().hex[:10].upper()}",
                "sender_id": structuring_user,
                "receiver_id": random.choice(USER_IDS[6:10]),
                "receiver_type": "user",
                "amount": round(random.uniform(200, 900), 2),
                "timestamp": datetime.utcnow().isoformat(),
                "device_id": DEVICE_IDS[2],
                "location": "Mombasa",
                "merchant_category": "general",
            }
        )

    return transactions


def main() -> None:
    transactions = generate_transactions()
    output = {
        "users": [{"user_id": u} for u in USER_IDS],
        "merchants": [
            {"merchant_id": m, "category": random.choice(CATEGORIES)} for m in MERCHANT_IDS
        ],
        "devices": [{"device_id": d} for d in DEVICE_IDS],
        "transactions": transactions,
    }
    print(json.dumps(output, indent=2))
    print(f"\n# Generated {len(transactions)} transactions for {NUM_USERS} users.")


if __name__ == "__main__":
    main()
