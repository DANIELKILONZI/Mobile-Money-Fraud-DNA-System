from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from app.core.storage import store
from app.graph.builder import graph_manager
from app.models.entities import Transaction, TransactionRequest, RiskResponse
from app.services.risk_engine import RiskEngine

router = APIRouter()
risk_engine = RiskEngine(store, graph_manager)


@router.post("/transaction", response_model=dict, status_code=201)
def ingest_transaction(req: TransactionRequest) -> dict:
    """Ingest a transaction and update the fraud graph."""
    timestamp = req.timestamp if req.timestamp else datetime.now(timezone.utc)

    tx = Transaction(
        tx_id=req.tx_id,
        sender_id=req.sender_id,
        receiver_id=req.receiver_id,
        amount=req.amount,
        timestamp=timestamp,
        device_id=req.device_id,
        location=req.location,
    )

    # Ensure entities exist
    store.get_or_create_user(req.sender_id)
    if req.receiver_type == "merchant":
        store.get_or_create_merchant(req.receiver_id, req.merchant_category or "general")
    else:
        store.get_or_create_user(req.receiver_id)
    if req.device_id:
        store.get_or_create_device(req.device_id)

    # Persist transaction
    store.add_transaction(tx)

    # Update graph
    graph_manager.add_transaction(tx, receiver_type=req.receiver_type)

    return {
        "status": "accepted",
        "tx_id": tx.tx_id,
        "message": "Transaction ingested and graph updated.",
    }


@router.get("/risk/user/{user_id}", response_model=RiskResponse)
def get_user_risk(user_id: str) -> dict:
    """Return risk score and explanation for a user."""
    if user_id not in store.users:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
    return risk_engine.score_user(user_id)


@router.get("/risk/merchant/{merchant_id}", response_model=RiskResponse)
def get_merchant_risk(merchant_id: str) -> dict:
    """Return risk score and explanation for a merchant."""
    if merchant_id not in store.merchants:
        raise HTTPException(status_code=404, detail=f"Merchant '{merchant_id}' not found")
    return risk_engine.score_merchant(merchant_id)


@router.get("/risk/transaction/{tx_id}", response_model=RiskResponse)
def get_transaction_risk(tx_id: str) -> dict:
    """Return risk score and explanation for a transaction."""
    if tx_id not in store.transactions:
        raise HTTPException(status_code=404, detail=f"Transaction '{tx_id}' not found")
    return risk_engine.score_transaction(tx_id)


@router.get("/graph/summary")
def get_graph_summary() -> dict:
    """Return graph statistics and top suspicious nodes."""
    summary = graph_manager.summary()

    # Score all known users and merchants, sort by risk
    scored: List[dict] = []
    for user_id in store.users:
        result = risk_engine.score_user(user_id)
        scored.append({
            "entity_id": user_id,
            "entity_type": "user",
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
        })
    for merchant_id in store.merchants:
        result = risk_engine.score_merchant(merchant_id)
        scored.append({
            "entity_id": merchant_id,
            "entity_type": "merchant",
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
        })

    scored.sort(key=lambda x: x["risk_score"], reverse=True)
    top_suspicious = [s for s in scored if s["risk_level"] != "LOW"][:10]

    return {
        "num_nodes": summary["num_nodes"],
        "num_edges": summary["num_edges"],
        "total_users": len(store.users),
        "total_merchants": len(store.merchants),
        "total_transactions": len(store.transactions),
        "top_suspicious_nodes": top_suspicious,
    }
