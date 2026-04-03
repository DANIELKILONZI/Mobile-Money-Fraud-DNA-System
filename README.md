<div align="center">

<!-- Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=EF4444,F97316,22C55E&height=200&section=header&text=Mobile%20Money%20Fraud%20DNA&fontSize=42&fontColor=ffffff&fontAlignY=38&desc=Behavioral%20%2B%20Graph%20Intelligence%20for%20Real-Time%20Fraud%20Detection&descSize=16&descAlignY=60" alt="Fraud DNA Banner"/>

<!-- Badges -->
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![NetworkX](https://img.shields.io/badge/NetworkX-Graph%20Analysis-orange?style=for-the-badge)](https://networkx.org/)
[![Tests](https://img.shields.io/badge/Tests-37%20Passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white)](#running-tests)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<br/>

> **"This is not one bad actor. This is a coordinated fraud ring."**

*The moment that sells the room.*

</div>

---

## 🧬 What Is This?

**Mobile Money Fraud DNA** is a production-grade fraud detection platform for M-Pesa–style mobile money systems. It ingests raw transactions and produces:

| Output | Description |
|--------|-------------|
| 🎯 **Risk Scores** | 0–1 score per user, merchant, or transaction |
| 📖 **Fraud Stories** | Human-readable narrative explaining exactly *why* a user is suspicious |
| 🌐 **Fraud Ring Detection** | Graph cycles revealing coordinated criminal networks |
| 🔔 **Structured Alerts** | Typed alerts (FRAUD_RING_DETECTED, STRUCTURING, etc.) with severity |
| 📊 **Live Graph Dashboard** | D3.js force-directed visualization — red clusters = money stolen |

> *"We plug into your transaction stream and reduce fraud losses using behavioral + graph intelligence — no changes to your core system."*

---

## 📦 Product Tiers

<div align="center">

| | 🧩 Risk Scoring API | 🧠 Intelligence Layer | 🌐 Graph Surveillance |
|---|---|---|---|
| **What it does** | Real-time fraud score per transaction / user / merchant | Fraud stories + behavioral insights + entity reputation | Fraud ring detection + cluster analysis + visual graph |
| **Key endpoint** | `GET /risk/user/{id}` | `fraud_story` in risk response | `GET /graph/suspicious-cluster/{id}` |
| **Who buys it** | Fintechs needing a score | Risk analysts needing context | Fraud ops teams needing the full picture |

</div>

---

## 🎬 WOW Demo Flow

> Run this before any pitch. Three API calls. One moment of silence.

### Setup

```bash
# Start the API
uvicorn app.main:app --reload

# Seed the demo scenario (one command)
python data/seed_demo.py
```

Or seed via HTTP:
```bash
curl -X POST http://localhost:8000/demo/seed
```

---

### Step 1 — The Normal User 🟢

```http
GET /risk/user/USER_CLEAN_001
```

```json
{
  "entity_id": "USER_CLEAN_001",
  "risk_score": 0.05,
  "risk_level": "LOW",
  "fraud_story": null,
  "alert": null,
  "reputation": { "trend": "STABLE", "long_term_score": 0.05 }
}
```

*"Here's what a legitimate customer looks like."*

---

### Step 2 — The Suspicious User 🔴

```http
GET /risk/user/USER_A
```

```json
{
  "entity_id": "USER_A",
  "risk_score": 0.91,
  "risk_level": "HIGH",
  "fraud_story": {
    "summary": "User is part of a suspected fraud ring involving 5 accounts; Shared device (DEV_SHARED_001) used by 6 users.",
    "chain": ["USER_A → USER_B → USER_C → USER_D → USER_E → USER_A"],
    "device_link": "Shared device (DEV_SHARED_001) used by 6 users",
    "pattern": "Circular fund movement + Device sharing"
  },
  "alert": { "alert_type": "FRAUD_RING_DETECTED", "severity": "HIGH" },
  "reputation": { "trend": "RISING", "long_term_score": 0.87 }
}
```

*"Notice the fraud story. The chain. The shared device. Not just a number — a narrative."*

---

### Step 3 — The Killer Move 💥

```http
GET /graph/suspicious-cluster/USER_A
```

```json
{
  "center_node": "USER_A",
  "cluster_risk": "HIGH",
  "nodes": [
    { "id": "USER_A", "risk_level": "HIGH",   "color": "red"    },
    { "id": "USER_B", "risk_level": "HIGH",   "color": "red"    },
    { "id": "USER_C", "risk_level": "MEDIUM", "color": "orange" },
    { "id": "USER_D", "risk_level": "HIGH",   "color": "red"    },
    { "id": "USER_E", "risk_level": "HIGH",   "color": "red"    }
  ],
  "edges": [
    { "source": "USER_A", "target": "USER_B", "tx_count": 2, "total_amount": 15500.0 },
    ...
  ]
}
```

> **"This is not one bad actor. This is a coordinated fraud ring."**
>
> 👉 *That moment = the buying trigger.*

---

### Visual Dashboard 📊

```
Open → http://localhost:8000/demo
```

The live D3.js dashboard renders in any browser. No frontend setup required.

```
🔴 Red nodes   = HIGH risk
🟠 Orange nodes = MEDIUM risk
🟢 Green nodes  = LOW risk
━━ Edge thickness = transaction volume
```

*Drag nodes. Hover for details. Click "Fraud ring" to load USER_A's cluster instantly.*

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                          │
│                                                                 │
│  POST /transaction ──► Storage ──► Graph Builder               │
│                                         │                      │
│  GET /risk/user/{id} ◄──────────────────┤                      │
│       │                            Risk Engine                 │
│       ├── Behavioral Features      (velocity + graph +         │
│       ├── Graph Features            device + amount)           │
│       ├── Fraud Story Builder                                  │
│       ├── Reputation Manager                                   │
│       └── Alert Generator                                      │
│                                                                 │
│  GET /graph/suspicious-cluster/{id} ──► Cluster Exporter       │
│  GET /demo ──────────────────────────► D3.js HTML Page         │
│  POST /demo/seed ────────────────────► Demo Seeder             │
└─────────────────────────────────────────────────────────────────┘
```

```
app/
├── api/
│   ├── routes.py           # Core API routes
│   └── demo_routes.py      # Demo seeder + D3.js visualization page
├── core/
│   └── storage.py          # In-memory state management
├── features/
│   ├── behavioral.py       # Velocity, burst, structuring features
│   └── graph_features.py   # Centrality, cycle, degree features
├── graph/
│   ├── builder.py          # NetworkX directed graph manager
│   └── cluster.py          # BFS subgraph exporter with risk annotation
├── models/
│   └── entities.py         # Pydantic v2 data models
├── services/
│   ├── fraud_patterns.py   # Rule-based fraud pattern detectors
│   ├── fraud_story.py      # Narrative builder (Fraud Story Mode)
│   ├── reputation.py       # EWMA long-term reputation scoring
│   └── risk_engine.py      # Hybrid scoring engine
└── main.py                 # FastAPI entry point
data/
├── generate_sample.py      # Synthetic dataset generator
└── seed_demo.py            # HTTP-based live demo seeder (CLI)
tests/
└── test_api.py             # 37 integration tests
```

---

## ⚙️ Tech Stack

<div align="center">

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI 0.111 |
| Graph Engine | NetworkX 3.3 |
| Data Layer | Pandas 2.2 + NumPy 1.26 |
| Visualization | D3.js v7 (bundled in HTML response) |
| Validation | Pydantic v2 |
| Server | Uvicorn |
| Testing | Pytest + HTTPX |
| Language | Python 3.10+ |

</div>

---

## 🚀 Quick Start

**1. Clone & install**
```bash
git clone https://github.com/DANIELKILONZI/Mobile-Money-Fraud-DNA-System.git
cd Mobile-Money-Fraud-DNA-System
pip install -r requirements.txt
```

**2. Start the API**
```bash
uvicorn app.main:app --reload
```

**3. Explore**

| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs` | Interactive Swagger UI |
| `http://localhost:8000/demo` | Live graph visualization |
| `http://localhost:8000/health` | Health check |

---

## 📡 API Reference

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
Returns full risk profile: score, level, reasons, fraud story, alert, reputation.

### `GET /risk/merchant/{merchant_id}`
Returns risk score and explanation for a merchant.

### `GET /risk/transaction/{tx_id}`
Returns risk score and explanation for a transaction.

### `GET /graph/summary`
Returns graph statistics and top 10 suspicious nodes by score.

### `GET /graph/suspicious-cluster/{node_id}?depth=2`
Returns a color-annotated subgraph centered on a node (BFS up to `depth` hops).

### `POST /demo/seed`
Seeds the in-memory store with the full pitch-ready demo scenario.

### `GET /demo`
Serves the interactive D3.js fraud graph visualization page.

---

## 🔬 Risk Intelligence Details

### Scoring Formula

```
risk_score = (
    velocity_anomaly  × 0.30   # burst of transactions in short window
  + graph_anomaly     × 0.40   # cycle detection, centrality
  + device_reuse      × 0.20   # shared device fingerprint
  + amount_outlier    × 0.10   # statistical outlier amounts
)
```

**Risk Levels:** `LOW` < 0.4 · `MEDIUM` 0.4–0.7 · `HIGH` ≥ 0.7

### Fraud Pattern Detectors

| Pattern | Trigger |
|---------|---------|
| 🔁 Circular flow | A → B → C → A detected in directed graph |
| 📱 Device reuse | Same device fingerprint used by > 5 distinct users |
| ⚡ Velocity spike | Transaction volume > 3× the entity's hourly baseline |
| 🏗️ Structuring | ≥ 5 transfers under 1,000 within 60 minutes |
| 🆕 New account abuse | Account < 24h old sends a transaction ≥ 50,000 |

### Fraud Story Format

```json
{
  "fraud_story": {
    "summary": "User is part of a suspected fraud ring involving 5 accounts; exhibits structuring behavior.",
    "chain":   ["USER_A → USER_B → USER_C → USER_D → USER_E → USER_A"],
    "device_link": "Shared device (DEV_SHARED_001) used by 6 users",
    "pattern": "Circular fund movement + Device sharing + Structuring"
  }
}
```

### Alert Types

| Alert | Severity |
|-------|---------|
| `FRAUD_RING_DETECTED` | HIGH |
| `STRUCTURING_DETECTED` | MEDIUM |
| `DEVICE_SHARING_DETECTED` | MEDIUM |
| `VELOCITY_SPIKE` | MEDIUM |
| `NEW_ACCOUNT_HIGH_VALUE` | HIGH |

---

## 🧪 Tests

```bash
python -m pytest tests/ -v
```

```
37 passed in 0.95s

  ✓ Health check
  ✓ Transaction ingestion (user & merchant)
  ✓ Risk scoring (user / merchant / transaction)
  ✓ Graph summary
  ✓ Device reuse, circular flow, structuring detection
  ✓ Behavioral & graph features
  ✓ Fraud story (present, absent, chain, device_link)
  ✓ Alerts (present, absent)
  ✓ Reputation scoring
  ✓ Suspicious cluster (404, subgraph, center node, depth)
  ✓ Demo seed (idempotent, fraud ring story, clean user)
  ✓ Demo page (HTML, D3.js graph)
```

---

## 🗂️ Generating Sample Data

```bash
python data/generate_sample.py
```

Produces a JSON dataset with 20 users, 5 merchants, 12 devices, and 80 transactions — including pre-baked fraud patterns (circular flow, device sharing, structuring) for immediate testing.

---

## 👤 Author

<div align="center">

<img src="https://avatars.githubusercontent.com/u/DANIELKILONZI?v=4" width="80" style="border-radius:50%" alt="Daniel Kimeu"/>

**Daniel Kimeu**

*Fraud Intelligence Engineer · Nairobi, Kenya*

[![GitHub](https://img.shields.io/badge/GitHub-DANIELKILONZI-181717?style=flat-square&logo=github)](https://github.com/DANIELKILONZI)

*Built with curiosity, caffeine, and a deep dislike of fraud rings.*

</div>

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=EF4444,F97316,22C55E&height=100&section=footer" alt="footer"/>

**Mobile Money Fraud DNA System** · © 2024 Daniel Kimeu · MIT License

*"People don't buy '0.87 risk score'. They buy 'That red cluster is stealing money'."*

</div>


