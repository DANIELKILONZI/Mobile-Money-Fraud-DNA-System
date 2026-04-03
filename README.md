# Mobile-Money-Fraud-DNA-System
Mobile Money Behavioral Risk Intelligence API

## Overview

A production-grade fraud detection and behavioral intelligence engine for mobile money transactions (M-Pesa-like systems). The system analyzes transaction behavior, builds a graph of interactions, and outputs real-time risk scores for users, merchants, transactions, and devices.

## Architecture

```
app/
├── api/
│   └── routes.py          # FastAPI route definitions
├── core/
│   └── storage.py         # In-memory state management
├── features/
│   ├── behavioral.py      # Behavioral feature engineering
│   └── graph_features.py  # Graph-based feature extraction
├── graph/
│   └── builder.py         # NetworkX directed graph manager
├── models/
│   └── entities.py        # Pydantic data models
├── services/
│   ├── fraud_patterns.py  # Rule-based fraud pattern detectors
│   └── risk_engine.py     # Hybrid risk scoring engine
└── main.py                # FastAPI application entry point
data/
└── generate_sample.py     # Synthetic dataset generator
tests/
└── test_api.py            # API integration tests
```

## Tech Stack

- **Python 3.10+**
- **FastAPI** — REST API layer
- **NetworkX** — Graph analysis (centrality, cycle detection)
- **Pandas / NumPy** — Data processing
- **Uvicorn** — ASGI server
- **Pydantic v2** — Data validation

## Installation

```bash
pip install -r requirements.txt
```

## Running the API

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

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
Returns risk score and explanation for a user (phone number).

### `GET /risk/merchant/{merchant_id}`
Returns risk score and explanation for a merchant.

### `GET /risk/transaction/{tx_id}`
Returns risk score and explanation for a specific transaction.

### `GET /graph/summary`
Returns graph statistics and top suspicious nodes.

## Risk Score Output Format

```json
{
  "entity_id": "+254700000001",
  "entity_type": "user",
  "risk_score": 0.72,
  "risk_level": "HIGH",
  "reasons": [
    "Circular money flow detected",
    "Device shared across 6 users"
  ],
  "features": {
    "freq_1h": 8,
    "burst_score": 1.0,
    "degree_centrality": 0.45,
    "in_cycle": true
  }
}
```

Risk levels: `LOW` (< 0.4), `MEDIUM` (0.4–0.7), `HIGH` (≥ 0.7)

## Risk Scoring Formula

```
risk_score = (
    velocity_anomaly * 0.3 +
    graph_anomaly   * 0.4 +
    device_reuse    * 0.2 +
    amount_outlier  * 0.1
)
```

## Fraud Pattern Detectors

| Pattern | Rule |
|---|---|
| Device reuse | Same device used by > 5 distinct users |
| Volume spike | Transaction volume > 3× hourly baseline |
| Circular flow | A → B → C → A cycle detected in graph |
| Structuring | ≥ 5 small transfers (< 1,000) in 60 minutes |
| New account high-value | Account < 24h old sends ≥ 50,000 transaction |

## Generating Sample Data

```bash
python data/generate_sample.py
```

Outputs a JSON dataset with synthetic users, merchants, devices, and transactions including pre-seeded fraud patterns for testing.

## Running Tests

```bash
python -m pytest tests/ -v
```
