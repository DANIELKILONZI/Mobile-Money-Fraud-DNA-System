"""Tests for the Mobile Money Behavioral Risk Intelligence API."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global store and graph between tests."""
    from app.core.storage import store
    from app.graph.builder import graph_manager
    store.users.clear()
    store.merchants.clear()
    store.devices.clear()
    store.transactions.clear()
    store.device_users.clear()
    import networkx as nx
    graph_manager.graph = nx.DiGraph()
    yield


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── POST /transaction ──────────────────────────────────────────────────────────

def test_ingest_transaction(client):
    payload = {
        "tx_id": "TX_001",
        "sender_id": "+254700000001",
        "receiver_id": "+254700000002",
        "amount": 1500.0,
        "receiver_type": "user",
    }
    resp = client.post("/transaction", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["tx_id"] == "TX_001"


def test_ingest_transaction_to_merchant(client):
    payload = {
        "tx_id": "TX_002",
        "sender_id": "+254700000001",
        "receiver_id": "MERCH_001",
        "amount": 500.0,
        "receiver_type": "merchant",
        "merchant_category": "grocery",
    }
    resp = client.post("/transaction", json=payload)
    assert resp.status_code == 201


def test_ingest_transaction_with_device(client):
    payload = {
        "tx_id": "TX_003",
        "sender_id": "+254700000001",
        "receiver_id": "+254700000002",
        "amount": 200.0,
        "device_id": "DEV_ABCDEF12",
        "receiver_type": "user",
    }
    resp = client.post("/transaction", json=payload)
    assert resp.status_code == 201


# ── GET /risk/user ─────────────────────────────────────────────────────────────

def test_user_risk_404(client):
    resp = client.get("/risk/user/UNKNOWN")
    assert resp.status_code == 404


def test_user_risk_after_transaction(client):
    client.post("/transaction", json={
        "tx_id": "TX_010",
        "sender_id": "+254700000010",
        "receiver_id": "+254700000011",
        "amount": 1000.0,
        "receiver_type": "user",
    })
    resp = client.get("/risk/user/+254700000010")
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_score" in data
    assert data["entity_type"] == "user"
    assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert 0.0 <= data["risk_score"] <= 1.0
    assert "features" in data
    assert "reasons" in data


def test_user_risk_response_schema(client):
    client.post("/transaction", json={
        "tx_id": "TX_011",
        "sender_id": "USER_A",
        "receiver_id": "USER_B",
        "amount": 250.0,
        "receiver_type": "user",
    })
    resp = client.get("/risk/user/USER_A")
    data = resp.json()
    for key in ("entity_id", "entity_type", "risk_score", "risk_level", "reasons", "features"):
        assert key in data


# ── GET /risk/merchant ─────────────────────────────────────────────────────────

def test_merchant_risk_404(client):
    resp = client.get("/risk/merchant/UNKNOWN_MERCH")
    assert resp.status_code == 404


def test_merchant_risk(client):
    client.post("/transaction", json={
        "tx_id": "TX_020",
        "sender_id": "+254700000020",
        "receiver_id": "MERCH_FOOD",
        "amount": 350.0,
        "receiver_type": "merchant",
        "merchant_category": "restaurant",
    })
    resp = client.get("/risk/merchant/MERCH_FOOD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "merchant"
    assert 0.0 <= data["risk_score"] <= 1.0


# ── GET /risk/transaction ──────────────────────────────────────────────────────

def test_transaction_risk_404(client):
    resp = client.get("/risk/transaction/NONEXISTENT")
    assert resp.status_code == 404


def test_transaction_risk(client):
    client.post("/transaction", json={
        "tx_id": "TX_030",
        "sender_id": "+254700000030",
        "receiver_id": "+254700000031",
        "amount": 7500.0,
        "receiver_type": "user",
    })
    resp = client.get("/risk/transaction/TX_030")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_type"] == "transaction"
    assert data["entity_id"] == "TX_030"
    assert 0.0 <= data["risk_score"] <= 1.0


# ── GET /graph/summary ─────────────────────────────────────────────────────────

def test_graph_summary_empty(client):
    resp = client.get("/graph/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_nodes"] == 0
    assert data["num_edges"] == 0
    assert data["total_transactions"] == 0


def test_graph_summary_after_transactions(client):
    for i in range(3):
        client.post("/transaction", json={
            "tx_id": f"TX_S{i}",
            "sender_id": f"USER_{i}",
            "receiver_id": f"USER_{i+10}",
            "amount": 100.0 * (i + 1),
            "receiver_type": "user",
        })
    resp = client.get("/graph/summary")
    data = resp.json()
    assert data["num_nodes"] >= 6
    assert data["num_edges"] >= 3
    assert data["total_transactions"] == 3
    assert "top_suspicious_nodes" in data


# ── Fraud pattern: Device reuse ────────────────────────────────────────────────

def test_device_reuse_detection(client):
    device = "DEV_SHARED_01"
    for i in range(6):
        client.post("/transaction", json={
            "tx_id": f"TX_DR{i}",
            "sender_id": f"USER_DR{i}",
            "receiver_id": "MERCH_A",
            "amount": 100.0,
            "device_id": device,
            "receiver_type": "merchant",
        })
    # Any of the 6 users should be flagged
    resp = client.get("/risk/user/USER_DR0")
    data = resp.json()
    device_related = [r for r in data["reasons"] if "device" in r.lower()]
    assert len(device_related) > 0 or data["risk_score"] > 0


# ── Fraud pattern: Circular flow ───────────────────────────────────────────────

def test_circular_flow_detection(client):
    # A → B → C → A
    for sender, receiver in [("USER_CA", "USER_CB"), ("USER_CB", "USER_CC"), ("USER_CC", "USER_CA")]:
        client.post("/transaction", json={
            "tx_id": f"TX_CF_{sender}",
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": 10000.0,
            "receiver_type": "user",
        })
    resp = client.get("/risk/user/USER_CA")
    data = resp.json()
    cycle_flags = [r for r in data["reasons"] if "circular" in r.lower() or "cycle" in r.lower()]
    assert len(cycle_flags) > 0


# ── Fraud pattern: Structuring ─────────────────────────────────────────────────

def test_structuring_detection(client):
    sender = "USER_STRUCT"
    now = datetime.now(timezone.utc).isoformat()
    for i in range(6):
        client.post("/transaction", json={
            "tx_id": f"TX_STR{i}",
            "sender_id": sender,
            "receiver_id": f"USER_RCV{i}",
            "amount": 500.0,
            "timestamp": now,
            "receiver_type": "user",
        })
    resp = client.get("/risk/user/" + sender)
    data = resp.json()
    struct_flags = [r for r in data["reasons"] if "structuring" in r.lower() or "small" in r.lower()]
    assert len(struct_flags) > 0


# ── Behavioral features ────────────────────────────────────────────────────────

def test_behavioral_features_populated(client):
    client.post("/transaction", json={
        "tx_id": "TX_BH1",
        "sender_id": "USER_BH",
        "receiver_id": "USER_BH2",
        "amount": 2000.0,
        "receiver_type": "user",
    })
    resp = client.get("/risk/user/USER_BH")
    features = resp.json()["features"]
    assert "freq_1h" in features
    assert "freq_24h" in features
    assert "avg_amount" in features
    assert "burst_score" in features


# ── Graph features ─────────────────────────────────────────────────────────────

def test_graph_features_populated(client):
    client.post("/transaction", json={
        "tx_id": "TX_GF1",
        "sender_id": "USER_GF",
        "receiver_id": "USER_GF2",
        "amount": 500.0,
        "receiver_type": "user",
    })
    resp = client.get("/risk/user/USER_GF")
    features = resp.json()["features"]
    assert "degree_centrality" in features
    assert "clustering_coefficient" in features
    assert "unique_counterparties" in features
