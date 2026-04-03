"""
Demo Seeder — seeds a running Fraud DNA API with a pitch-ready demo scenario.

Usage:
    python data/seed_demo.py [--base-url http://localhost:8000]

After running, use this exact demo flow:

  Step 1 — Normal user
    GET /risk/user/USER_CLEAN_001      → LOW risk, stable reputation, no alerts

  Step 2 — Suspicious user
    GET /risk/user/USER_A              → HIGH risk, fraud_story, alert triggered

  Step 3 — THE KILLER MOVE
    GET /graph/suspicious-cluster/USER_A  → the fraud ring, visualized

  Visual dashboard:
    Open http://localhost:8000/demo    → force-directed graph, color-coded nodes
"""

import argparse
import json
import sys

try:
    import httpx
except ImportError:
    import urllib.request as _req  # noqa: F401 — fallback available in stdlib

BASE_URL = "http://localhost:8000"


def post(session, path: str, payload: dict) -> dict:
    resp = session.post(f"{BASE_URL}{path}", json=payload)
    resp.raise_for_status()
    return resp.json()


def get(session, path: str) -> dict:
    resp = session.get(f"{BASE_URL}{path}")
    resp.raise_for_status()
    return resp.json()


def main(base_url: str) -> None:
    global BASE_URL
    BASE_URL = base_url.rstrip("/")

    import httpx
    with httpx.Client(timeout=30) as session:
        print(f"\n🔗  Target API: {BASE_URL}")

        # ── Verify health ──────────────────────────────────────────────────────
        health = get(session, "/health")
        assert health["status"] == "ok", "API not healthy"
        print("✅  Health check passed\n")

        # ── Seed via the built-in endpoint ────────────────────────────────────
        print("🌱  Seeding demo data via POST /demo/seed …")
        seed_result = post(session, "/demo/seed", {})
        print(f"    Status : {seed_result['status']}")
        demo_users = seed_result["demo_users"]
        print(f"    Users  : {json.dumps(demo_users, indent=6)}\n")

        # ── Step 1: Clean user ─────────────────────────────────────────────────
        clean_id = demo_users["clean_user"]
        print(f"📋  STEP 1 — Clean user ({clean_id})")
        risk = get(session, f"/risk/user/{clean_id}")
        print(f"    Risk score : {risk['risk_score']}")
        print(f"    Risk level : {risk['risk_level']}")
        print(f"    Alert      : {risk.get('alert')}")
        print(f"    Fraud story: {risk.get('fraud_story')}\n")

        # ── Step 2: Suspicious user ────────────────────────────────────────────
        ring_id = demo_users["fraud_ring_entry"]
        print(f"🔴  STEP 2 — Suspicious user ({ring_id})")
        risk = get(session, f"/risk/user/{ring_id}")
        print(f"    Risk score : {risk['risk_score']}")
        print(f"    Risk level : {risk['risk_level']}")
        if risk.get("alert"):
            print(f"    ⚠  Alert   : {risk['alert']['alert_type']} [{risk['alert']['severity']}]")
        if risk.get("fraud_story"):
            s = risk["fraud_story"]
            print(f"    📖 Summary : {s['summary']}")
            for chain in s.get("chain", []):
                print(f"       Chain   : {chain}")
            print(f"       Pattern : {s['pattern']}")
        print()

        # ── Step 3: The cluster ────────────────────────────────────────────────
        print(f"🌐  STEP 3 — Fraud ring cluster (/graph/suspicious-cluster/{ring_id})")
        cluster = get(session, f"/graph/suspicious-cluster/{ring_id}")
        print(f"    Cluster risk : {cluster['cluster_risk']}")
        print(f"    Nodes        : {len(cluster['nodes'])}")
        print(f"    Edges        : {len(cluster['edges'])}")
        high_nodes = [n for n in cluster["nodes"] if n["risk_level"] == "HIGH"]
        print(f"    🔴 HIGH nodes: {[n['id'] for n in high_nodes]}")
        print()
        print("💬  PITCH LINE:")
        print(f'    "{seed_result["pitch_line"]}"')
        print()
        print(f"📊  Open the visual dashboard → {BASE_URL}/demo")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Fraud DNA demo scenario")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the running API (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    try:
        main(args.base_url)
    except Exception as exc:
        print(f"\n❌  Error: {exc}", file=sys.stderr)
        print(
            "\nMake sure the API is running:\n"
            "  uvicorn app.main:app --reload\n",
            file=sys.stderr,
        )
        sys.exit(1)
