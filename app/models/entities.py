from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(BaseModel):
    user_id: str
    created_at: datetime = Field(default_factory=_utcnow)


class Merchant(BaseModel):
    merchant_id: str
    category: str = "general"


class Device(BaseModel):
    device_id: str


class Transaction(BaseModel):
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: float
    timestamp: datetime = Field(default_factory=_utcnow)
    device_id: Optional[str] = None
    location: Optional[str] = None


class TransactionRequest(BaseModel):
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: float
    timestamp: Optional[datetime] = None
    device_id: Optional[str] = None
    location: Optional[str] = None
    receiver_type: str = "user"
    merchant_category: Optional[str] = "general"


class FraudStory(BaseModel):
    summary: str
    chain: list[str]
    device_link: Optional[str] = None
    pattern: str


class Alert(BaseModel):
    alert_type: str
    severity: str


class ReputationInfo(BaseModel):
    long_term_score: float
    score_count: int
    trend: str  # "RISING", "STABLE", "FALLING"


class RiskResponse(BaseModel):
    entity_id: str
    entity_type: str
    risk_score: float
    risk_level: str
    reasons: list[str]
    features: dict
    fraud_story: Optional[FraudStory] = None
    alert: Optional[Alert] = None
    reputation: Optional[ReputationInfo] = None
