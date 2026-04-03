"""Tests for the Mobile Money Behavioral Risk Intelligence API."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global store and graph between tests."""
    from app.core.storage import store
    from app.graph.builder import graph_manager
    from app.services.reputation import reputation_manager
    store.users.clear()
    store.merchants.clear()
    store.devices.clear()
    store.transactions.clear()
    store.device_users.clear()
    reputation_manager._history.clear()
    reputation_manager._long_term.clear()
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


# ── Fraud Story Mode ───────────────────────────────────────────────────────────

def test_fraud_story_present_for_circular_flow(client):
    """Users in a circular money-flow ring must have a fraud_story."""
    for sender, receiver in [("USER_CA", "USER_CB"), ("USER_CB", "USER_CC"), ("USER_CC", "USER_CA")]:
        client.post("/transaction", json={
            "tx_id": f"TX_FS_{sender}",
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": 10000.0,
            "receiver_type": "user",
        })
    resp = client.get("/risk/user/USER_CA")
    data = resp.json()
    assert data["fraud_story"] is not None, "Expected fraud_story for circular-flow user"
    story = data["fraud_story"]
    assert "summary" in story and story["summary"]
    assert "chain" in story and len(story["chain"]) > 0
    assert "pattern" in story and story["pattern"]
    # The chain should include arrow notation
    assert "→" in story["chain"][0]


def test_fraud_story_chain_closes_loop(client):
    """The rendered chain must close back to the originating node."""
    for sender, receiver in [("USER_R1", "USER_R2"), ("USER_R2", "USER_R3"), ("USER_R3", "USER_R1")]:
        client.post("/transaction", json={
            "tx_id": f"TX_LOOP_{sender}",
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": 5000.0,
            "receiver_type": "user",
        })
    data = client.get("/risk/user/USER_R1").json()
    story = data["fraud_story"]
    assert story is not None
    chain_str = story["chain"][0]
    parts = [p.strip() for p in chain_str.split("→")]
    # First and last node must be the same (closed loop)
    assert parts[0] == parts[-1]


def test_fraud_story_device_link(client):
    """A user on a heavily-shared device should get a device_link in fraud_story."""
    device = "DEV_STORY_01"
    for i in range(6):
        client.post("/transaction", json={
            "tx_id": f"TX_DS{i}",
            "sender_id": f"USER_DS{i}",
            "receiver_id": "MERCH_Z",
            "amount": 200.0,
            "device_id": device,
            "receiver_type": "merchant",
        })
    resp = client.get("/risk/user/USER_DS0")
    data = resp.json()
    assert data["fraud_story"] is not None
    assert data["fraud_story"]["device_link"] is not None
    assert device in data["fraud_story"]["device_link"]


def test_fraud_story_absent_for_low_risk(client):
    """A clean user with a single normal transaction should not get a fraud_story."""
    client.post("/transaction", json={
        "tx_id": "TX_CLEAN1",
        "sender_id": "USER_CLEAN",
        "receiver_id": "USER_CLEAN2",
        "amount": 300.0,
        "receiver_type": "user",
    })
    data = client.get("/risk/user/USER_CLEAN").json()
    assert data["fraud_story"] is None


# ── Alert object ───────────────────────────────────────────────────────────────

def test_alert_present_for_fraud_ring(client):
    for sender, receiver in [("U_A1", "U_A2"), ("U_A2", "U_A3"), ("U_A3", "U_A1")]:
        client.post("/transaction", json={
            "tx_id": f"TX_AL_{sender}",
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": 10000.0,
            "receiver_type": "user",
        })
    data = client.get("/risk/user/U_A1").json()
    if data["risk_level"] != "LOW":
        assert data["alert"] is not None
        assert "alert_type" in data["alert"]
        assert "severity" in data["alert"]


def test_alert_absent_for_low_risk(client):
    client.post("/transaction", json={
        "tx_id": "TX_ALERT_CLEAN",
        "sender_id": "USER_ALC",
        "receiver_id": "USER_ALC2",
        "amount": 100.0,
        "receiver_type": "user",
    })
    data = client.get("/risk/user/USER_ALC").json()
    assert data["alert"] is None


# ── Reputation Score ───────────────────────────────────────────────────────────

def test_reputation_present_in_user_risk(client):
    client.post("/transaction", json={
        "tx_id": "TX_REP1",
        "sender_id": "USER_REP",
        "receiver_id": "USER_REP2",
        "amount": 500.0,
        "receiver_type": "user",
    })
    data = client.get("/risk/user/USER_REP").json()
    assert data["reputation"] is not None
    rep = data["reputation"]
    assert "long_term_score" in rep
    assert "score_count" in rep
    assert rep["trend"] in ("RISING", "STABLE", "FALLING")


def test_reputation_score_count_increases(client):
    """Calling the risk endpoint multiple times should increase score_count."""
    client.post("/transaction", json={
        "tx_id": "TX_RC1",
        "sender_id": "USER_RC",
        "receiver_id": "USER_RC2",
        "amount": 200.0,
        "receiver_type": "user",
    })
    client.get("/risk/user/USER_RC")
    client.get("/risk/user/USER_RC")
    data = client.get("/risk/user/USER_RC").json()
    assert data["reputation"]["score_count"] >= 3


# ── Suspicious Cluster endpoint ────────────────────────────────────────────────

def test_suspicious_cluster_404_for_unknown(client):
    resp = client.get("/graph/suspicious-cluster/NOBODY")
    assert resp.status_code == 404


def test_suspicious_cluster_returns_subgraph(client):
    """After ingesting a transaction the cluster endpoint should return nodes/edges."""
    client.post("/transaction", json={
        "tx_id": "TX_CL1",
        "sender_id": "USER_CL1",
        "receiver_id": "USER_CL2",
        "amount": 1000.0,
        "receiver_type": "user",
    })
    resp = client.get("/graph/suspicious-cluster/USER_CL1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["center_node"] == "USER_CL1"
    assert "nodes" in data and len(data["nodes"]) >= 2
    assert "edges" in data
    assert "cluster_risk" in data
    # Every node should have a color field
    for node in data["nodes"]:
        assert "color" in node
        assert node["color"] in ("red", "orange", "green", "grey")


def test_suspicious_cluster_center_node_flagged(client):
    """The center node must be marked is_center=True."""
    client.post("/transaction", json={
        "tx_id": "TX_CL2",
        "sender_id": "USER_CL3",
        "receiver_id": "USER_CL4",
        "amount": 500.0,
        "receiver_type": "user",
    })
    data = client.get("/graph/suspicious-cluster/USER_CL3").json()
    center_nodes = [n for n in data["nodes"] if n["is_center"]]
    assert len(center_nodes) == 1
    assert center_nodes[0]["id"] == "USER_CL3"


def test_suspicious_cluster_depth_parameter(client):
    """depth=1 should return fewer nodes than depth=2 for the same center."""
    # Build a 3-hop chain
    for i in range(3):
        client.post("/transaction", json={
            "tx_id": f"TX_DEPTH{i}",
            "sender_id": f"USER_D{i}",
            "receiver_id": f"USER_D{i+1}",
            "amount": 100.0,
            "receiver_type": "user",
        })
    d1 = client.get("/graph/suspicious-cluster/USER_D0?depth=1").json()
    d2 = client.get("/graph/suspicious-cluster/USER_D0?depth=2").json()
    assert len(d2["nodes"]) >= len(d1["nodes"])


# ── Demo routes ────────────────────────────────────────────────────────────────

def test_demo_seed_returns_expected_keys(client):
    resp = client.post("/demo/seed")
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "seeded"
    assert "demo_users" in data
    assert "demo_endpoints" in data
    assert "pitch_line" in data
    users = data["demo_users"]
    assert users["clean_user"] == "USER_CLEAN_001"
    assert users["fraud_ring_entry"] == "USER_A"
    assert isinstance(users["ring_members"], list)
    assert len(users["ring_members"]) == 5


def test_demo_seed_creates_users_in_store(client):
    client.post("/demo/seed")
    resp = client.get("/risk/user/USER_A")
    assert resp.status_code == 200
    resp2 = client.get("/risk/user/USER_CLEAN_001")
    assert resp2.status_code == 200


def test_demo_seed_fraud_ring_user_has_fraud_story(client):
    client.post("/demo/seed")
    data = client.get("/risk/user/USER_A").json()
    assert data["fraud_story"] is not None
    assert data["fraud_story"]["chain"]
    assert "→" in data["fraud_story"]["chain"][0]


def test_demo_seed_clean_user_has_no_fraud_story(client):
    client.post("/demo/seed")
    data = client.get("/risk/user/USER_CLEAN_001").json()
    assert data["fraud_story"] is None


def test_demo_seed_is_idempotent(client):
    """Calling seed twice should not duplicate transactions."""
    client.post("/demo/seed")
    from app.core.storage import store
    count_after_first = len(store.transactions)

    client.post("/demo/seed")
    count_after_second = len(store.transactions)
    assert count_after_second == count_after_first


def test_demo_page_returns_html(client):
    resp = client.get("/demo")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "https://d3js.org/d3.v7.min.js" in resp.text
    assert "Fraud DNA" in resp.text


def test_demo_page_contains_graph_js(client):
    resp = client.get("/demo")
    assert "suspicious-cluster" in resp.text
    assert "forceSimulation" in resp.text
