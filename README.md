# Mobile Money Fraud DNA System
**Behavioral + Graph Intelligence for Mobile Money Fraud Detection**

> *"We plug into your transaction stream and reduce fraud losses using behavioral + graph intelligence — no changes to your core system."*

---

## What This Does

A production-grade fraud detection engine for mobile money (M-Pesa-like) systems. It combines **behavioral analytics**, **graph cycle detection**, and **explainable AI narratives** to turn raw transactions into actionable intelligence.

---

## Product Tiers

| Tier | Offering | Key Endpoint |
|------|----------|--------------|
| 🧩 **Risk Scoring API** | Real-time fraud score per transaction / user / merchant | `GET /risk/user/{id}` |
| 🧠 **Intelligence Layer** | Fraud stories, behavioral insights, entity reputation | `GET /risk/user/{id}` → `fraud_story` |
| 🌐 **Graph Surveillance** | Fraud ring detection, cluster analysis, visual graph | `GET /graph/suspicious-cluster/{id}` |

---

## 🎬 WOW Demo Flow (3 steps)

**Setup — seed the demo in one call:**
```bash
# Terminal 1 — start the API
uvicorn app.main:app --reload

# Terminal 2 — seed the demo scenario
python data/seed_demo.py
```

**Step 1 — Normal user**
```
GET /risk/user/USER_CLEAN_001
→ LOW risk, stable reputation, no alerts, no fraud story
```

**Step 2 — Suspicious user**
```
GET /risk/user/USER_A
→ HIGH risk, fraud_story with chain, alert triggered, reputation rising
```

**Step 3 — THE KILLER MOVE**
```
GET /graph/suspicious-cluster/USER_A
→ Full fraud ring, color-coded nodes, edge weights
```

Then say: **"This is not one bad actor. This is a coordinated fraud ring."**

**Visual Dashboard**
```
Open http://localhost:8000/demo
→ D3.js force-directed graph, red = HIGH risk, interactive tooltips
```

---

## Architecture

```
app/
├── api/
│   ├── routes.py           # Core API routes
│   └── demo_routes.py      # Demo seeder + visualization page
├── core/
│   └── storage.py          # In-memory state management
├── features/
│   ├── behavioral.py       # Behavioral feature engineering
│   └── graph_features.py   # Graph-based feature extraction
├── graph/
│   ├── builder.py          # NetworkX directed graph manager
│   └── cluster.py          # Suspicious cluster subgraph exporter
├── models/
│   └── entities.py         # Pydantic data models
├── services/
│   ├── fraud_patterns.py   # Rule-based fraud pattern detectors
│   ├── fraud_story.py      # Fraud Story Mode narrative builder
│   ├── reputation.py       # Entity reputation (EWMA long-term score)
│   └── risk_engine.py      # Hybrid risk scoring engine
└── main.py                 # FastAPI application entry point
data/
├── generate_sample.py      # Synthetic dataset generator
└── seed_demo.py            # Live demo seeder (HTTP-based)
tests/
└── test_api.py             # API integration tests (37 tests)
```

---

## Tech Stack

- **Python 3.10+**
- **FastAPI** — REST API layer
- **NetworkX** — Graph analysis (centrality, cycle detection)
- **Pandas / NumPy** — Data processing
- **D3.js** — In-browser force-directed graph visualization
- **Uvicorn** — ASGI server
- **Pydantic v2** — Data validation

---

## Installation

```bash
pip install -r requirements.txt
```

## Running the API

```bash
uvicorn app.main:app --reload
```

API: `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs`  
Visual demo: `http://localhost:8000/demo`

---

## API Endpoints

### `POST /transaction`
Ingest a transaction and update the fraud graph.

```json
{
  "tx_id": "TX_001",
  "sender_id": "+254700000001",
  "receiver_id": "+254700000002",
  "amount": 1500.0,
  "receiver_type": "user",
  "device_id": "DEV_ABC123",
  "location": "Nairobi"
}
```

### `GET /risk/user/{user_id}`
Returns risk score, fraud story, alert, and reputation for a user.

### `GET /risk/merchant/{merchant_id}`
Returns risk score and explanation for a merchant.

### `GET /risk/transaction/{tx_id}`
Returns risk score and explanation for a specific transaction.

### `GET /graph/summary`
Returns graph statistics and top suspicious nodes.

### `GET /graph/suspicious-cluster/{node_id}?depth=2`
Returns a color-annotated subgraph centered on a node (BFS up to `depth` hops).  
Node colors: 🔴 red = HIGH, 🟠 orange = MEDIUM, 🟢 green = LOW.

### `POST /demo/seed`
Seeds the in-memory store with a ready-made demo scenario (fraud ring + clean user + structuring user).

### `GET /demo`
Serves the interactive D3.js fraud graph visualization page.

---

## Risk Score Output Format

```json
{
  "entity_id": "+254700000001",
  "entity_type": "user",
  "risk_score": 0.91,
  "risk_level": "HIGH",
  "reasons": [
    "Circular money flow detected involving this entity",
    "Device shared across 6 users"
  ],
  "features": {
    "freq_1h": 8,
    "burst_score": 1.0,
    "degree_centrality": 0.45,
    "in_cycle": true
  },
  "fraud_story": {
    "summary": "User is part of a suspected fraud ring involving 5 accounts; exhibits structuring behavior.",
    "chain": ["USER_A → USER_B → USER_C → USER_D → USER_E → USER_A"],
    "device_link": "Shared device (DEV_SHARED_001) used by 6 users",
    "pattern": "Circular fund movement + Device sharing + Structuring"
  },
  "alert": {
    "alert_type": "FRAUD_RING_DETECTED",
    "severity": "HIGH"
  },
  "reputation": {
    "long_term_score": 0.87,
    "score_count": 12,
    "trend": "RISING"
  }
}
```

Risk levels: `LOW` (< 0.4), `MEDIUM` (0.4–0.7), `HIGH` (≥ 0.7)

---

## Risk Scoring Formula

```
risk_score = (
    velocity_anomaly * 0.3 +
    graph_anomaly   * 0.4 +
    device_reuse    * 0.2 +
    amount_outlier  * 0.1
)
```

---

## Fraud Pattern Detectors

| Pattern | Rule |
|---|---|
| Device reuse | Same device used by > 5 distinct users |
| Volume spike | Transaction volume > 3× hourly baseline |
| Circular flow | A → B → C → A cycle detected in graph |
| Structuring | ≥ 5 small transfers (< 1,000) in 60 minutes |
| New account high-value | Account < 24h old sends ≥ 50,000 transaction |

---

## Generating Sample Data

```bash
python data/generate_sample.py
```

Outputs a JSON dataset with synthetic users, merchants, devices, and transactions including pre-seeded fraud patterns.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

37 tests covering all endpoints, fraud patterns, fraud story, reputation, alerts, cluster export, and demo routes.

