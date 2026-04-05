<div align="center">

<!-- Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=EF4444,F97316,22C55E&height=200&section=header&text=Mobile%20Money%20Fraud%20DNA&fontSize=42&fontColor=ffffff&fontAlignY=38&desc=Behavioral%20%2B%20Graph%20Intelligence%20for%20Real-Time%20Fraud%20Detection&descSize=16&descAlignY=60" alt="Fraud DNA Banner"/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![NetworkX](https://img.shields.io/badge/NetworkX-Graph%20Analysis-orange?style=for-the-badge)](https://networkx.org/)
[![Tests](https://img.shields.io/badge/Tests-37%20Passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white)](#tests)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

</div>

---

## What Is This?

M-Pesa and similar mobile money networks process millions of transactions a day across East Africa. Most are legitimate. Some are not — and the fraudulent ones tend to operate in coordinated patterns: shared devices, circular fund movement between colluding accounts, rapid small transfers designed to stay under reporting thresholds.

**Mobile Money Fraud DNA** is a FastAPI-based fraud detection engine built for exactly this environment. It ingests raw transactions, builds a directed transaction graph, and scores every user, merchant, and transaction in real time using a combination of behavioral analytics and graph-theoretic features.

The output is not just a number. Each risk response includes a **fraud story** — a human-readable explanation of *why* the score is what it is, what pattern was detected, and which accounts are connected to it.

| Output | Description |
|--------|-------------|
| **Risk score** | 0–1 float per entity, updated on every transaction |
| **Fraud story** | Narrative summary: ring membership, device links, patterns |
| **Structured alert** | Typed alert with severity (`FRAUD_RING_DETECTED`, `STRUCTURING_DETECTED`, etc.) |
| **Long-term reputation** | EWMA-smoothed score tracking each entity's risk over time |
| **Graph cluster** | BFS subgraph export for visualization or downstream analysis |

---

## How It Works

### Scoring Pipeline

Every call to `GET /risk/user/{id}` runs the full pipeline:

1. **Behavioral features** — transaction frequency in the last 1h / 24h / 7d, average and standard-deviation of amounts, burst detection (>5 transactions in 10 minutes), and a night-time anomaly flag (transactions between midnight and 5am).

2. **Graph features** — degree centrality, in/out degree, clustering coefficient, unique counterparty count, and whether the entity sits inside a money-flow cycle.

3. **Pattern detection** — five rule-based detectors run against the live graph and transaction store.

4. **Weighted score** — the four sub-scores are combined:

```
risk_score = velocity_anomaly × 0.30
           + graph_anomaly    × 0.40
           + device_reuse     × 0.20
           + amount_outlier   × 0.10
```

Graph anomaly carries the highest weight because cycle membership is the strongest indicator of coordinated fraud in mobile money networks.

5. **Fraud story & alert** — if the score is elevated, a narrative is built from the detected signals and a typed alert is emitted.

6. **Reputation update** — the score is fed into an EWMA tracker (α = 0.3) that maintains a long-term risk trend for each entity across queries.

**Risk thresholds:** `LOW` < 0.4 · `MEDIUM` 0.4–0.7 · `HIGH` ≥ 0.7

---

### Fraud Pattern Detectors

| Pattern | How it triggers |
|---------|-----------------|
| **Circular flow** | `networkx.simple_cycles` on the directed transaction graph (device nodes excluded); any cycle of length ≤ 5 involving this entity |
| **Device reuse** | Same `device_id` used by more than 5 distinct senders |
| **Velocity spike** | Transactions in the last hour exceed 3× the entity's hourly baseline (hours 2–25) |
| **Structuring** | ≥ 5 transfers each below KES 1,000 within a 60-minute window |
| **New-account high value** | Account age < 24 hours and at least one transaction ≥ KES 50,000 |

### Fraud Story

When patterns are detected the engine builds a `fraud_story` object:

```json
{
  "summary": "User is part of a suspected fraud ring involving 5 accounts; Shared device (DEV_SHARED_001) used by 6 users.",
  "chain": ["USER_A → USER_B → USER_C → USER_D → USER_E → USER_A"],
  "device_link": "Shared device (DEV_SHARED_001) used by 6 users",
  "pattern": "Circular fund movement + Device sharing"
}
```

`fraud_story` is `null` for clean entities — no noise for low-risk users.

### Reputation Tracking

The `ReputationManager` keeps a rolling history (capped at 50 observations) per entity and computes a long-term score using an exponentially weighted moving average:

```
long_term_score = α × current_score + (1 − α) × previous_long_term   # α = 0.3
```

The trend (`RISING` / `STABLE` / `FALLING`) is derived by comparing the average of the last 3 scores against the historical average. A rising trend on a high-risk entity is a stronger signal than a single spike.

---

## Graph Model

The underlying graph is a `networkx.DiGraph`. Each transaction adds:
- A directed edge from `sender_id` → `receiver_id` (aggregated: `tx_count`, `total_amount`)
- A directed edge from `sender_id` → `device_id` (type: `used_device`)

Cycle detection operates on a device-filtered subgraph so that shared-device hubs don't create false cycles. The cluster exporter uses BFS up to a configurable depth to extract a color-annotated subgraph for visualization.

---

## Demo

Seed a pre-built scenario (clean user, 5-node fraud ring, structuring user) and walk through the three main endpoints:

```bash
# 1. Start the API
uvicorn app.main:app --reload

# 2. Seed the demo data
curl -X POST http://localhost:8000/demo/seed

# 3. A clean user — score near zero, no story, no alert
curl http://localhost:8000/risk/user/USER_CLEAN_001

# 4. A fraud-ring member — score ~0.91, full fraud story, FRAUD_RING_DETECTED alert
curl http://localhost:8000/risk/user/USER_A

# 5. The network around USER_A — color-annotated subgraph
curl "http://localhost:8000/graph/suspicious-cluster/USER_A?depth=2"
```

The seeder also creates `USER_STRUCT_001` with 6 small transfers in quick succession — enough to trigger the structuring detector.

### Visual Dashboard

```
http://localhost:8000/demo
```

A D3.js force-directed graph renders directly in the browser — no build step, no frontend setup. Nodes are colored by risk level (red / orange / green), edge thickness encodes transaction volume, and hovering a node shows its score and type. The sidebar displays the live fraud story and alert for whatever node you're inspecting.

---

## Quick Start

```bash
git clone https://github.com/DANIELKILONZI/Mobile-Money-Fraud-DNA-System.git
cd Mobile-Money-Fraud-DNA-System
pip install -r requirements.txt
uvicorn app.main:app --reload
```

| URL | What you get |
|-----|--------------|
| `http://localhost:8000/docs` | Auto-generated Swagger UI for all endpoints |
| `http://localhost:8000/demo` | Live D3.js fraud graph dashboard |
| `http://localhost:8000/health` | Health check |

---

## API Reference

### `POST /transaction`
Ingest a transaction. Updates the graph and behavioral store immediately.

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
Full risk profile: score, level, reasons, behavioral and graph features, fraud story, alert, reputation.

### `GET /risk/merchant/{merchant_id}`
Risk score for a merchant based on incoming transaction volume and graph position.

### `GET /risk/transaction/{tx_id}`
Risk score for a specific transaction — inherits 50% from sender risk, 30% from device reuse, 20% from amount outlier.

### `GET /graph/summary`
Node and edge counts plus top-10 suspicious nodes by score.

### `GET /graph/suspicious-cluster/{node_id}?depth=2`
BFS subgraph centered on `node_id`, annotated with per-node risk level and score.

### `POST /demo/seed`
(Re-)seeds the in-memory store with the demo scenario. Idempotent.

### `GET /demo`
Interactive D3.js visualization page.

---

## Project Structure

```
app/
├── api/
│   ├── routes.py          # Core API endpoints
│   └── demo_routes.py     # Demo seeder + D3.js visualization
├── core/
│   └── storage.py         # In-memory state (users, merchants, devices, transactions)
├── features/
│   ├── behavioral.py      # Velocity, burst, time-anomaly, amount-deviation features
│   └── graph_features.py  # Centrality, cycle membership, shared-device count
├── graph/
│   ├── builder.py         # NetworkX DiGraph manager
│   └── cluster.py         # BFS subgraph exporter
├── models/
│   └── entities.py        # Pydantic v2 data models
├── services/
│   ├── fraud_patterns.py  # Rule-based pattern detectors
│   ├── fraud_story.py     # Narrative builder
│   ├── reputation.py      # EWMA long-term reputation tracker
│   └── risk_engine.py     # Scoring engine — wires everything together
└── main.py                # FastAPI entry point

data/
├── generate_sample.py     # Synthetic dataset generator (20 users, 80 transactions)
└── seed_demo.py           # CLI demo seeder (calls POST /demo/seed)

tests/
└── test_api.py            # 37 integration tests (TestClient, synchronous)
```

---

## Tech Stack

| Layer | Library |
|-------|---------|
| API framework | FastAPI 0.111 + Uvicorn |
| Graph engine | NetworkX 3.3 |
| Data models | Pydantic v2.7 |
| Numerical | Pandas 2.2, NumPy 1.26 |
| Visualization | D3.js v7 (inlined in HTML response) |
| Testing | Pytest 8.2 + HTTPX |
| Language | Python 3.10+ |

---

## Tests

```bash
python -m pytest tests/ -v
```

```
37 passed in ~1s

  Health check
  Transaction ingestion (user, merchant)
  Risk scoring (user, merchant, transaction)
  Graph summary + suspicious-cluster (404, depth, center node)
  Pattern detection (device reuse, circular flow, structuring)
  Behavioral + graph features
  Fraud story (present, absent, chain, device_link)
  Alerts (present, absent, all types)
  Reputation (EWMA score, trend)
  Demo seed (idempotent, fraud ring, clean user)
  Demo page (HTML, D3.js content)
```

Tests use FastAPI's `TestClient` (synchronous) and reset all global state via an `autouse` fixture before each run.

---

## Generating Sample Data

```bash
python data/generate_sample.py
```

Generates a JSON dataset with 20 users, 5 merchants, 12 devices, and 80 transactions. The dataset includes pre-seeded fraud patterns — circular fund flows, shared devices, and structuring sequences — so it can be loaded directly for testing or exploration.

---

## Author

<div align="center">

<img src="https://github.com/DANIELKILONZI.png" width="80" style="border-radius:50%" alt="Daniel Kimeu"/>

**Daniel Kimeu** · Fraud Intelligence Engineer · Nairobi, Kenya

[![GitHub](https://img.shields.io/badge/GitHub-DANIELKILONZI-181717?style=flat-square&logo=github)](https://github.com/DANIELKILONZI)

</div>

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=EF4444,F97316,22C55E&height=100&section=footer" alt="footer"/>

**Mobile Money Fraud DNA System** · © 2024 Daniel Kimeu · MIT License

</div>


