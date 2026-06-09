# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=1.0.0",
#     "openai>=1.50.0",
#     "pydantic>=2.0.0",
#     "sqlalchemy>=2.0.0",
# ]
# ///
"""
mcp_virtual_wallet_demo.py

Plataforma fintech de billetera virtual con integración MCP (Model Context Protocol).

Arquitectura:
  Este demo implementa una plataforma completa de wallet virtual donde MCP actúa
  como capa de integración unificada entre el sistema core bancario y los agentes
  de IA que operan sobre él.

  Componentes:
  ┌─────────────────────────────────────────────────────────────────┐
  │                     MCP Server (Fintech Core)                   │
  │  ┌───────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
  │  │ SQLAlchemy │  │ Fraud Engine │  │ Transaction Processor   │ │
  │  │   Models   │  │ (Rule+ML)   │  │ (Accounts/Cards/Txns)   │ │
  │  └───────────┘  └──────────────┘  └─────────────────────────┘ │
  │                                                                 │
  │  Tools: analyze_transaction, detect_fraud_patterns,             │
  │         get_account_summary, generate_spending_insights,        │
  │         block_suspicious_card, create_dispute                   │
  │                                                                 │
  │  Resources: transactions://recent, fraud://alerts               │
  └─────────────────────────────────────────────────────────────────┘
          │ stdio / SSE
          ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                   MCP Client (Agent Orchestrator)               │
  │  ┌──────────────┐  ┌────────────────┐  ┌───────────────────┐  │
  │  │ Fraud Agent   │  │ Support Agent  │  │ Advisor Agent     │  │
  │  │ (monitoreo    │  │ (disputas y    │  │ (insights         │  │
  │  │  en tiempo    │  │  consultas)    │  │  financieros)     │  │
  │  │  real)        │  │                │  │                   │  │
  │  └──────────────┘  └────────────────┘  └───────────────────┘  │
  └─────────────────────────────────────────────────────────────────┘

  En producción, MCP habilita integración con:
  - Procesadores de pago (Stripe, Adyen, dLocal)
  - Redes bancarias (SWIFT, ACH, CBU/CVU)
  - Burós de crédito (Veraz, Nosis)
  - APIs de compliance (KYC/AML, listas OFAC)
  - Sistemas de notificación (SMS, push, email)

  Consideraciones de producción NO implementadas en demo:
  - PCI DSS compliance (tokenización de PAN, encriptación en tránsito/reposo)
  - HSM (Hardware Security Module) para claves criptográficas
  - Audit log inmutable (append-only, firmado digitalmente)
  - Rate limiting y circuit breakers para APIs externas
  - Idempotency keys para transacciones financieras
  - Strong customer authentication (SCA / 3DS2)

Ejecución demo:     uv run 01_python_frameworks/mcp_virtual_wallet_demo.py
Ejecución servidor: uv run 01_python_frameworks/mcp_virtual_wallet_demo.py --serve
"""

import os
import sys
import json
import math
import uuid
from enum import Enum
from datetime import datetime, timezone, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import (
    create_engine, Column, String, Float, DateTime, Boolean,
    Enum as SAEnum, ForeignKey, Text, select, desc,
)
from sqlalchemy.orm import (
    DeclarativeBase, Session, relationship, sessionmaker,
)
from mcp.server.fastmcp import FastMCP


# ==========================================
# MODELOS DE DATOS (Pydantic)
# ==========================================

class TransactionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    REVERSED = "reversed"
    DISPUTED = "disputed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class CardStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    REPORTED_STOLEN = "reported_stolen"


class TransactionAnalysis(BaseModel):
    transaction_id: str
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    flags: list[str]
    recommendation: str
    velocity_check: dict
    geo_check: dict


class SpendingInsight(BaseModel):
    user_id: str
    period: str
    total_spent: float
    categories: dict[str, float]
    trend: str
    tips: list[str]
    anomaly_alerts: list[str]


# ==========================================
# MODELOS DE BASE DE DATOS (SQLAlchemy)
# ==========================================

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(20), nullable=True)
    kyc_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    accounts = relationship("Account", back_populates="user")
    cards = relationship("Card", back_populates="user")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    currency = Column(String(3), default="ARS")
    balance = Column(Float, default=0.0)
    available_balance = Column(Float, default=0.0)
    account_type = Column(String(20), default="checking")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")


class Card(Base):
    __tablename__ = "cards"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    last_four = Column(String(4), nullable=False)
    card_type = Column(String(20), default="debit")
    status = Column(SAEnum(CardStatus), default=CardStatus.ACTIVE)
    daily_limit = Column(Float, default=50000.0)
    monthly_limit = Column(Float, default=500000.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    blocked_at = Column(DateTime, nullable=True)
    block_reason = Column(Text, nullable=True)

    user = relationship("User", back_populates="cards")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    card_id = Column(String, ForeignKey("cards.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="ARS")
    merchant = Column(String(255), nullable=True)
    category = Column(String(50), nullable=True)
    status = Column(SAEnum(TransactionStatus), default=TransactionStatus.PENDING)
    risk_score = Column(Float, default=0.0)
    ip_address = Column(String(45), nullable=True)
    geo_location = Column(String(100), nullable=True)
    device_fingerprint = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    account = relationship("Account", back_populates="transactions")
    fraud_alerts = relationship("FraudAlert", back_populates="transaction")
    disputes = relationship("Dispute", back_populates="transaction")


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(SAEnum(RiskLevel), nullable=False)
    flags = Column(Text, default="[]")
    status = Column(SAEnum(AlertStatus), default=AlertStatus.OPEN)
    analyst_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    transaction = relationship("Transaction", back_populates="fraud_alerts")


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    amount_claimed = Column(Float, nullable=False)
    status = Column(String(30), default="open")
    resolution = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    transaction = relationship("Transaction", back_populates="disputes")


# ==========================================
# INICIALIZACIÓN DE BASE DE DATOS
# ==========================================

engine = create_engine("sqlite:///:memory:", echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_database() -> None:
    Base.metadata.create_all(engine)
    session = SessionLocal()

    now = datetime.now(timezone.utc)

    users = [
        User(id="user-001", name="María García", email="maria@email.com", phone="+5491112345678", kyc_verified=True),
        User(id="user-002", name="Carlos López", email="carlos@email.com", phone="+5491187654321", kyc_verified=True),
        User(id="user-003", name="Ana Martínez", email="ana@email.com", phone="+5491155556666", kyc_verified=False),
    ]
    session.add_all(users)

    accounts = [
        Account(id="acc-001", user_id="user-001", balance=245000.00, available_balance=245000.00, currency="ARS"),
        Account(id="acc-002", user_id="user-002", balance=89500.50, available_balance=89500.50, currency="ARS"),
        Account(id="acc-003", user_id="user-003", balance=12300.00, available_balance=12300.00, currency="ARS"),
    ]
    session.add_all(accounts)

    cards = [
        Card(id="card-001", user_id="user-001", last_four="4242", card_type="debit", daily_limit=100000),
        Card(id="card-002", user_id="user-001", last_four="5555", card_type="credit", daily_limit=200000),
        Card(id="card-003", user_id="user-002", last_four="1234", card_type="debit", daily_limit=50000),
        Card(id="card-004", user_id="user-003", last_four="9876", card_type="debit", daily_limit=30000),
    ]
    session.add_all(cards)

    transactions = [
        Transaction(id="txn-001", account_id="acc-001", card_id="card-001", amount=1500.00, merchant="Mercado Libre", category="ecommerce", status=TransactionStatus.APPROVED, risk_score=0.1, geo_location="-34.60,-58.38", created_at=now - timedelta(hours=48)),
        Transaction(id="txn-002", account_id="acc-001", card_id="card-002", amount=45000.00, merchant="Electronics Store", category="electronics", status=TransactionStatus.APPROVED, risk_score=0.3, geo_location="-34.60,-58.38", created_at=now - timedelta(hours=24)),
        Transaction(id="txn-003", account_id="acc-001", card_id="card-001", amount=890.00, merchant="Supermercado Coto", category="groceries", status=TransactionStatus.APPROVED, risk_score=0.05, geo_location="-34.60,-58.38", created_at=now - timedelta(hours=12)),
        Transaction(id="txn-004", account_id="acc-001", card_id="card-002", amount=185000.00, merchant="Unknown Merchant XY", category="unknown", status=TransactionStatus.PENDING, risk_score=0.85, ip_address="185.220.101.42", geo_location="52.52,13.40", device_fingerprint="fp_suspicious_01", created_at=now - timedelta(minutes=5)),
        Transaction(id="txn-005", account_id="acc-001", card_id="card-001", amount=95000.00, merchant="Crypto Exchange ABC", category="crypto", status=TransactionStatus.PENDING, risk_score=0.92, ip_address="185.220.101.42", geo_location="52.52,13.40", device_fingerprint="fp_suspicious_01", created_at=now - timedelta(minutes=3)),
        Transaction(id="txn-006", account_id="acc-002", card_id="card-003", amount=3200.00, merchant="Farmacity", category="pharmacy", status=TransactionStatus.APPROVED, risk_score=0.05, geo_location="-34.59,-58.39", created_at=now - timedelta(hours=6)),
        Transaction(id="txn-007", account_id="acc-002", card_id="card-003", amount=12000.00, merchant="Restaurante Don Julio", category="dining", status=TransactionStatus.APPROVED, risk_score=0.15, geo_location="-34.59,-58.39", created_at=now - timedelta(hours=3)),
        Transaction(id="txn-008", account_id="acc-003", card_id="card-004", amount=75000.00, merchant="Wire Transfer Intl", category="transfer", status=TransactionStatus.PENDING, risk_score=0.78, ip_address="103.25.41.88", geo_location="1.35,103.82", created_at=now - timedelta(minutes=10)),
        Transaction(id="txn-009", account_id="acc-001", card_id="card-001", amount=2100.00, merchant="Spotify Premium", category="subscriptions", status=TransactionStatus.APPROVED, risk_score=0.02, geo_location="-34.60,-58.38", created_at=now - timedelta(days=3)),
        Transaction(id="txn-010", account_id="acc-001", card_id="card-002", amount=67000.00, merchant="Apple Store", category="electronics", status=TransactionStatus.APPROVED, risk_score=0.2, geo_location="-34.60,-58.38", created_at=now - timedelta(days=5)),
    ]
    session.add_all(transactions)

    alerts = [
        FraudAlert(id="alert-001", transaction_id="txn-004", user_id="user-001", risk_score=0.85, risk_level=RiskLevel.HIGH, flags=json.dumps(["geo_anomaly", "high_amount", "unknown_merchant", "velocity_exceeded"]), status=AlertStatus.OPEN, created_at=now - timedelta(minutes=5)),
        FraudAlert(id="alert-002", transaction_id="txn-005", user_id="user-001", risk_score=0.92, risk_level=RiskLevel.CRITICAL, flags=json.dumps(["crypto_transaction", "geo_anomaly", "velocity_exceeded", "new_device", "amount_spike"]), status=AlertStatus.OPEN, created_at=now - timedelta(minutes=3)),
        FraudAlert(id="alert-003", transaction_id="txn-008", user_id="user-003", risk_score=0.78, risk_level=RiskLevel.HIGH, flags=json.dumps(["international_transfer", "unverified_kyc", "high_amount_relative"]), status=AlertStatus.INVESTIGATING, created_at=now - timedelta(minutes=10)),
    ]
    session.add_all(alerts)

    session.commit()
    session.close()


# ==========================================
# MOTOR DE DETECCIÓN DE FRAUDE
# ==========================================

HOME_GEO = {"user-001": (-34.60, -58.38), "user-002": (-34.59, -58.39), "user-003": (-34.61, -58.37)}

HIGH_RISK_CATEGORIES = {"crypto", "gambling", "wire_transfer", "unknown"}

SUSPICIOUS_MERCHANT_KEYWORDS = ["unknown", "crypto", "offshore", "anonymous"]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _compute_velocity(session: Session, account_id: str, window_minutes: int = 60) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    recent = session.execute(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.created_at >= cutoff,
        )
    ).scalars().all()
    total = sum(t.amount for t in recent)
    return {
        "window_minutes": window_minutes,
        "transaction_count": len(recent),
        "total_amount": round(total, 2),
        "avg_amount": round(total / len(recent), 2) if recent else 0,
    }


def _compute_geo_distance(session: Session, txn: Transaction) -> dict:
    user = session.execute(select(User).join(Account).where(Account.id == txn.account_id)).scalar_one()
    home = HOME_GEO.get(user.id, (-34.60, -58.38))
    if txn.geo_location:
        parts = txn.geo_location.split(",")
        txn_lat, txn_lon = float(parts[0]), float(parts[1])
        distance_km = _haversine_km(home[0], home[1], txn_lat, txn_lon)
    else:
        distance_km = 0.0
    return {
        "home_location": f"{home[0]},{home[1]}",
        "transaction_location": txn.geo_location or "unknown",
        "distance_km": round(distance_km, 1),
        "is_anomalous": distance_km > 500,
    }


def analyze_transaction_logic(session: Session, transaction_id: str) -> TransactionAnalysis:
    txn = session.execute(select(Transaction).where(Transaction.id == transaction_id)).scalar_one_or_none()
    if not txn:
        return TransactionAnalysis(
            transaction_id=transaction_id, risk_score=1.0, risk_level=RiskLevel.CRITICAL,
            flags=["transaction_not_found"], recommendation="RECHAZAR — transacción inexistente",
            velocity_check={}, geo_check={},
        )

    flags: list[str] = []
    score = 0.0

    if txn.amount > 50000:
        score += 0.2
        flags.append("high_amount")
    if txn.amount > 100000:
        score += 0.15
        flags.append("very_high_amount")

    if txn.category in HIGH_RISK_CATEGORIES:
        score += 0.25
        flags.append(f"high_risk_category:{txn.category}")

    if txn.merchant:
        for kw in SUSPICIOUS_MERCHANT_KEYWORDS:
            if kw in txn.merchant.lower():
                score += 0.15
                flags.append("suspicious_merchant")
                break

    velocity = _compute_velocity(session, txn.account_id)
    if velocity["transaction_count"] >= 3:
        score += 0.15
        flags.append("velocity_exceeded")
    if velocity["total_amount"] > 200000:
        score += 0.1
        flags.append("high_velocity_amount")

    geo = _compute_geo_distance(session, txn)
    if geo["is_anomalous"]:
        score += 0.25
        flags.append("geo_anomaly")

    if txn.ip_address and txn.ip_address.startswith(("185.", "103.", "45.")):
        score += 0.1
        flags.append("suspicious_ip")

    if txn.device_fingerprint and "suspicious" in txn.device_fingerprint:
        score += 0.15
        flags.append("new_device")

    account = session.execute(select(Account).where(Account.id == txn.account_id)).scalar_one()
    user = session.execute(select(User).where(User.id == account.user_id)).scalar_one()
    if not user.kyc_verified and txn.amount > 30000:
        score += 0.2
        flags.append("unverified_kyc_high_amount")

    score = min(score, 1.0)

    if score >= 0.8:
        level = RiskLevel.CRITICAL
        recommendation = "BLOQUEAR inmediatamente. Escalar a equipo de fraude. Notificar al usuario."
    elif score >= 0.6:
        level = RiskLevel.HIGH
        recommendation = "Retener transacción. Solicitar autenticación adicional (3DS/OTP)."
    elif score >= 0.3:
        level = RiskLevel.MEDIUM
        recommendation = "Monitorear. Permitir con alerta al sistema de compliance."
    else:
        level = RiskLevel.LOW
        recommendation = "Aprobar. Sin indicadores de riesgo significativos."

    txn.risk_score = score
    session.commit()

    return TransactionAnalysis(
        transaction_id=transaction_id,
        risk_score=round(score, 2),
        risk_level=level,
        flags=flags,
        recommendation=recommendation,
        velocity_check=velocity,
        geo_check=geo,
    )


def detect_fraud_patterns_logic(session: Session, user_id: str, time_range_hours: int = 24) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)
    accounts = session.execute(select(Account).where(Account.user_id == user_id)).scalars().all()
    account_ids = [a.id for a in accounts]

    txns = session.execute(
        select(Transaction).where(
            Transaction.account_id.in_(account_ids),
            Transaction.created_at >= cutoff,
        ).order_by(Transaction.created_at)
    ).scalars().all()

    if not txns:
        return {"user_id": user_id, "patterns_found": 0, "patterns": [], "risk_assessment": "Sin actividad en el período."}

    patterns: list[dict] = []

    amounts = [t.amount for t in txns]
    avg_amount = sum(amounts) / len(amounts)
    spikes = [t for t in txns if t.amount > avg_amount * 3]
    if spikes:
        patterns.append({
            "type": "amount_spike",
            "severity": "high",
            "description": f"{len(spikes)} transaccion(es) con monto >3x el promedio (${avg_amount:,.0f})",
            "transactions": [s.id for s in spikes],
        })

    geo_locations = set()
    for t in txns:
        if t.geo_location:
            geo_locations.add(t.geo_location)
    if len(geo_locations) > 2:
        patterns.append({
            "type": "multi_geo",
            "severity": "medium",
            "description": f"Transacciones desde {len(geo_locations)} ubicaciones geográficas distintas",
            "locations": list(geo_locations),
        })

    for i in range(1, len(txns)):
        delta = (txns[i].created_at - txns[i - 1].created_at).total_seconds()
        if delta < 300:
            patterns.append({
                "type": "rapid_sequence",
                "severity": "high",
                "description": f"Transacciones con <5 min de diferencia: {txns[i-1].id} -> {txns[i].id} ({delta:.0f}s)",
                "transactions": [txns[i - 1].id, txns[i].id],
            })
            break

    categories_used = set(t.category for t in txns if t.category)
    if "crypto" in categories_used or "unknown" in categories_used:
        patterns.append({
            "type": "high_risk_categories",
            "severity": "critical",
            "description": f"Categorías de alto riesgo detectadas: {categories_used & HIGH_RISK_CATEGORIES}",
            "transactions": [t.id for t in txns if t.category in HIGH_RISK_CATEGORIES],
        })

    devices = set(t.device_fingerprint for t in txns if t.device_fingerprint)
    if len(devices) > 2:
        patterns.append({
            "type": "multiple_devices",
            "severity": "medium",
            "description": f"{len(devices)} dispositivos distintos usados en {time_range_hours}h",
            "devices": list(devices),
        })

    overall_risk = "low"
    severities = [p["severity"] for p in patterns]
    if "critical" in severities:
        overall_risk = "critical"
    elif "high" in severities:
        overall_risk = "high"
    elif "medium" in severities:
        overall_risk = "medium"

    return {
        "user_id": user_id,
        "time_range_hours": time_range_hours,
        "total_transactions": len(txns),
        "total_amount": round(sum(amounts), 2),
        "patterns_found": len(patterns),
        "patterns": patterns,
        "risk_assessment": overall_risk,
    }


def generate_spending_insights_logic(session: Session, user_id: str) -> SpendingInsight:
    accounts = session.execute(select(Account).where(Account.user_id == user_id)).scalars().all()
    account_ids = [a.id for a in accounts]

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    txns = session.execute(
        select(Transaction).where(
            Transaction.account_id.in_(account_ids),
            Transaction.created_at >= thirty_days_ago,
            Transaction.status == TransactionStatus.APPROVED,
        )
    ).scalars().all()

    categories: dict[str, float] = {}
    for t in txns:
        cat = t.category or "other"
        categories[cat] = categories.get(cat, 0) + t.amount

    total_spent = sum(categories.values())

    tips: list[str] = []
    anomalies: list[str] = []

    if categories.get("dining", 0) > total_spent * 0.3 and total_spent > 0:
        tips.append("Tu gasto en restaurantes supera el 30% del total. Considerá establecer un presupuesto mensual.")

    if categories.get("subscriptions", 0) > 5000:
        tips.append("Revisá tus suscripciones activas — estás gastando más de $5.000/mes en servicios recurrentes.")

    if categories.get("ecommerce", 0) > 20000:
        tips.append("Tus compras online son significativas. Aprovechá cashback y programas de puntos.")

    if total_spent > 100000:
        tips.append("Tu gasto mensual es elevado. Considerá separar un porcentaje a inversiones automáticas.")

    tips.append("Activá notificaciones de gasto para mantener visibilidad de tus transacciones en tiempo real.")

    if categories.get("crypto", 0) > 0:
        anomalies.append(f"Detectamos compras de crypto por ${categories['crypto']:,.0f} — verificá que sean operaciones autorizadas.")

    if categories.get("unknown", 0) > 0:
        anomalies.append(f"Hay ${categories['unknown']:,.0f} en comercios no categorizados — revisá si reconocés estas transacciones.")

    trend = "estable"
    if total_spent > 200000:
        trend = "creciente — gasto mensual elevado"
    elif total_spent < 50000:
        trend = "moderado — dentro de parámetros normales"

    return SpendingInsight(
        user_id=user_id,
        period="últimos 30 días",
        total_spent=round(total_spent, 2),
        categories={k: round(v, 2) for k, v in sorted(categories.items(), key=lambda x: -x[1])},
        trend=trend,
        tips=tips,
        anomaly_alerts=anomalies,
    )


# ==========================================
# MCP SERVER — DEFINICIÓN
# ==========================================

mcp = FastMCP("virtual-wallet")


@mcp.tool()
def analyze_transaction(transaction_id: str) -> dict:
    """Analiza una transacción individual para detectar fraude.
    Retorna risk_score (0-1), flags detectadas, verificación de velocidad
    y geolocalización, y recomendación de acción."""
    session = SessionLocal()
    try:
        result = analyze_transaction_logic(session, transaction_id)
        return result.model_dump()
    finally:
        session.close()


@mcp.tool()
def get_account_summary(user_id: str) -> dict:
    """Obtiene resumen completo de cuenta: saldo, transacciones recientes,
    patrones de gasto y estado de tarjetas."""
    session = SessionLocal()
    try:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            return {"error": f"Usuario '{user_id}' no encontrado."}

        accounts = session.execute(select(Account).where(Account.user_id == user_id)).scalars().all()
        cards = session.execute(select(Card).where(Card.user_id == user_id)).scalars().all()

        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_txns = []
        for acc in accounts:
            txns = session.execute(
                select(Transaction).where(
                    Transaction.account_id == acc.id,
                    Transaction.created_at >= seven_days_ago,
                ).order_by(desc(Transaction.created_at)).limit(10)
            ).scalars().all()
            for t in txns:
                recent_txns.append({
                    "id": t.id, "amount": t.amount, "merchant": t.merchant,
                    "category": t.category, "status": t.status.value,
                    "risk_score": t.risk_score, "created_at": t.created_at.isoformat(),
                })

        recent_txns.sort(key=lambda x: x["created_at"], reverse=True)

        spending_by_category: dict[str, float] = {}
        for acc in accounts:
            txns = session.execute(
                select(Transaction).where(
                    Transaction.account_id == acc.id,
                    Transaction.created_at >= seven_days_ago,
                    Transaction.status == TransactionStatus.APPROVED,
                )
            ).scalars().all()
            for t in txns:
                cat = t.category or "other"
                spending_by_category[cat] = spending_by_category.get(cat, 0) + t.amount

        alerts = session.execute(
            select(FraudAlert).where(
                FraudAlert.user_id == user_id,
                FraudAlert.status.in_([AlertStatus.OPEN, AlertStatus.INVESTIGATING]),
            )
        ).scalars().all()

        return {
            "user": {"id": user.id, "name": user.name, "email": user.email, "kyc_verified": user.kyc_verified},
            "accounts": [{"id": a.id, "balance": a.balance, "available": a.available_balance, "currency": a.currency} for a in accounts],
            "cards": [{"id": c.id, "last_four": c.last_four, "type": c.card_type, "status": c.status.value} for c in cards],
            "recent_transactions": recent_txns[:15],
            "spending_7d": {k: round(v, 2) for k, v in spending_by_category.items()},
            "active_alerts": len(alerts),
        }
    finally:
        session.close()


@mcp.tool()
def detect_fraud_patterns(user_id: str, time_range_hours: int = 24) -> dict:
    """Detecta patrones de fraude en las transacciones de un usuario.
    Analiza: picos de monto, multi-geolocalización, secuencias rápidas,
    categorías de alto riesgo y uso de múltiples dispositivos."""
    session = SessionLocal()
    try:
        return detect_fraud_patterns_logic(session, user_id, time_range_hours)
    finally:
        session.close()


@mcp.tool()
def generate_spending_insights(user_id: str) -> dict:
    """Genera insights financieros personalizados para un usuario.
    Incluye desglose por categoría, tendencias, consejos y alertas de anomalías."""
    session = SessionLocal()
    try:
        result = generate_spending_insights_logic(session, user_id)
        return result.model_dump()
    finally:
        session.close()


@mcp.tool()
def block_suspicious_card(card_id: str, reason: str) -> dict:
    """Bloquea una tarjeta por actividad sospechosa.
    En producción: notifica al usuario vía push/SMS, registra en audit log,
    y genera request de reemisión automática."""
    session = SessionLocal()
    try:
        card = session.execute(select(Card).where(Card.id == card_id)).scalar_one_or_none()
        if not card:
            return {"error": f"Tarjeta '{card_id}' no encontrada."}
        if card.status == CardStatus.BLOCKED:
            return {"status": "already_blocked", "card_id": card_id, "message": "La tarjeta ya se encuentra bloqueada."}

        card.status = CardStatus.BLOCKED
        card.blocked_at = datetime.now(timezone.utc)
        card.block_reason = reason
        session.commit()

        user = session.execute(select(User).where(User.id == card.user_id)).scalar_one()

        return {
            "status": "blocked",
            "card_id": card_id,
            "last_four": card.last_four,
            "user_id": user.id,
            "user_name": user.name,
            "reason": reason,
            "blocked_at": card.blocked_at.isoformat(),
            "next_steps": [
                "Notificación push enviada al usuario",
                "SMS de confirmación enviado",
                "Tarjeta de reemisión generada automáticamente",
                "Ticket de soporte creado para seguimiento",
            ],
        }
    finally:
        session.close()


@mcp.tool()
def create_dispute(transaction_id: str, reason: str) -> dict:
    """Crea un reclamo/disputa sobre una transacción.
    En producción: inicia flujo de chargeback con la red (Visa/Mastercard),
    congela fondos del merchant, y asigna caso a analista."""
    session = SessionLocal()
    try:
        txn = session.execute(select(Transaction).where(Transaction.id == transaction_id)).scalar_one_or_none()
        if not txn:
            return {"error": f"Transacción '{transaction_id}' no encontrada."}

        account = session.execute(select(Account).where(Account.id == txn.account_id)).scalar_one()

        dispute = Dispute(
            transaction_id=transaction_id,
            user_id=account.user_id,
            reason=reason,
            amount_claimed=txn.amount,
            status="under_review",
        )
        txn.status = TransactionStatus.DISPUTED
        session.add(dispute)
        session.commit()

        return {
            "dispute_id": dispute.id,
            "transaction_id": transaction_id,
            "user_id": account.user_id,
            "amount_claimed": txn.amount,
            "reason": reason,
            "status": "under_review",
            "estimated_resolution": "5-10 días hábiles",
            "next_steps": [
                "Transacción marcada como disputada",
                "Fondos retenidos preventivamente",
                "Caso asignado a analista de fraude",
                "Notificación al merchant iniciada",
                "Chargeback iniciado con red de pago" if txn.card_id else "Reclamo interno en proceso",
            ],
        }
    finally:
        session.close()


@mcp.resource("transactions://recent")
def recent_transactions_resource() -> str:
    """Últimas transacciones de todos los usuarios del sistema."""
    session = SessionLocal()
    try:
        txns = session.execute(
            select(Transaction).order_by(desc(Transaction.created_at)).limit(20)
        ).scalars().all()
        results = []
        for t in txns:
            results.append({
                "id": t.id, "account_id": t.account_id, "amount": t.amount,
                "merchant": t.merchant, "category": t.category,
                "status": t.status.value, "risk_score": t.risk_score,
                "geo_location": t.geo_location,
                "created_at": t.created_at.isoformat(),
            })
        return json.dumps(results, indent=2, ensure_ascii=False)
    finally:
        session.close()


@mcp.resource("fraud://alerts")
def fraud_alerts_resource() -> str:
    """Alertas de fraude activas en el sistema."""
    session = SessionLocal()
    try:
        alerts = session.execute(
            select(FraudAlert).where(
                FraudAlert.status.in_([AlertStatus.OPEN, AlertStatus.INVESTIGATING])
            ).order_by(desc(FraudAlert.risk_score))
        ).scalars().all()
        results = []
        for a in alerts:
            results.append({
                "id": a.id, "transaction_id": a.transaction_id,
                "user_id": a.user_id, "risk_score": a.risk_score,
                "risk_level": a.risk_level.value,
                "flags": json.loads(a.flags) if isinstance(a.flags, str) else a.flags,
                "status": a.status.value,
                "created_at": a.created_at.isoformat(),
            })
        return json.dumps(results, indent=2, ensure_ascii=False)
    finally:
        session.close()


# ==========================================
# AGENTES DE IA (Orquestación del Cliente MCP)
# ==========================================

def _call_llm(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "[LLM no disponible — modo mock]"

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[Error LLM: {e}]"


def fraud_detection_agent():
    print("\n" + "=" * 60)
    print("  AGENTE DE DETECCIÓN DE FRAUDE")
    print("  Monitoreo en tiempo real de transacciones")
    print("=" * 60)

    print("\n--- Paso 1: Consultando alertas activas (fraud://alerts) ---")
    alerts_data = json.loads(fraud_alerts_resource())
    print(f"   Alertas activas encontradas: {len(alerts_data)}")
    for alert in alerts_data:
        print(f"   [{alert['id']}] txn={alert['transaction_id']} risk={alert['risk_score']} "
              f"level={alert['risk_level']} flags={alert['flags']}")

    print("\n--- Paso 2: Analizando transacción de mayor riesgo (txn-005) ---")
    analysis = analyze_transaction("txn-005")
    print(f"   Risk Score: {analysis['risk_score']} ({analysis['risk_level']})")
    print(f"   Flags: {analysis['flags']}")
    print(f"   Recomendación: {analysis['recommendation']}")
    print(f"   Velocity: {json.dumps(analysis['velocity_check'], ensure_ascii=False)}")
    print(f"   Geo: {json.dumps(analysis['geo_check'], ensure_ascii=False)}")

    print("\n--- Paso 3: Detectando patrones de fraude para user-001 ---")
    patterns = detect_fraud_patterns("user-001", time_range_hours=24)
    print(f"   Transacciones analizadas: {patterns['total_transactions']}")
    print(f"   Patrones encontrados: {patterns['patterns_found']}")
    print(f"   Riesgo general: {patterns['risk_assessment']}")
    for p in patterns.get("patterns", []):
        print(f"   [{p['type']}] severity={p['severity']} — {p['description']}")

    print("\n--- Paso 4: Respuesta automática — Bloqueando tarjeta comprometida ---")
    block_result = block_suspicious_card("card-002", "Actividad fraudulenta detectada: transacciones desde geolocalización anómala con montos inusuales")
    print(f"   Estado: {block_result['status']}")
    print(f"   Tarjeta: ****{block_result.get('last_four', 'N/A')}")
    for step in block_result.get("next_steps", []):
        print(f"   -> {step}")

    print("\n--- Paso 5: Análisis con IA ---")
    llm_response = _call_llm(
        "Sos un analista senior de fraude financiero. Respondé en español, conciso y profesional.",
        "Analizá este caso de fraude:\n"
        "- Usuario: María García (user-001)\n"
        "- Transacciones sospechosas: txn-004 ($185.000) y txn-005 ($95.000)\n"
        "- Risk scores: 0.85 y 0.92\n"
        "- Flags: geo_anomaly, high_amount, unknown_merchant, crypto_transaction, velocity_exceeded\n"
        "- Origen: IP 185.220.101.42, geolocalización Berlín (muy lejos de Buenos Aires)\n"
        "- Dispositivo: fingerprint nuevo, no visto antes\n"
        "¿Qué acciones adicionales recomendás más allá del bloqueo de tarjeta?",
    )
    if llm_response != "[LLM no disponible — modo mock]":
        print(f"   [Fraud Agent - LLM]:\n   {llm_response}")
    else:
        print("   [Fraud Agent - Mock] Recomendaciones del analista:")
        print("   1. Contactar al usuario para confirmar las transacciones")
        print("   2. Iniciar chargeback con Visa/Mastercard para ambas transacciones")
        print("   3. Reportar IP 185.220.101.42 a Threat Intelligence")
        print("   4. Revisar si el device_fingerprint aparece en otras cuentas")
        print("   5. Escalar a compliance para reporte a UIF si corresponde")


def customer_support_agent():
    print("\n" + "=" * 60)
    print("  AGENTE DE SOPORTE AL CLIENTE")
    print("  Gestión de disputas y consultas")
    print("=" * 60)

    print("\n--- Paso 1: Obteniendo resumen de cuenta del usuario afectado ---")
    summary = get_account_summary("user-001")
    print(f"   Usuario: {summary['user']['name']} (KYC: {'✓' if summary['user']['kyc_verified'] else '✗'})")
    for acc in summary["accounts"]:
        print(f"   Cuenta {acc['id']}: ${acc['balance']:,.2f} {acc['currency']}")
    for card in summary["cards"]:
        print(f"   Tarjeta ****{card['last_four']}: {card['type']} — {card['status']}")
    print(f"   Alertas activas: {summary['active_alerts']}")

    print("\n--- Paso 2: Creando disputa por transacción fraudulenta ---")
    dispute = create_dispute("txn-004", "Transacción no reconocida — posible clonación de tarjeta. El usuario niega haber realizado esta compra.")
    print(f"   Dispute ID: {dispute['dispute_id']}")
    print(f"   Monto reclamado: ${dispute['amount_claimed']:,.2f}")
    print(f"   Resolución estimada: {dispute['estimated_resolution']}")
    for step in dispute.get("next_steps", []):
        print(f"   -> {step}")

    print("\n--- Paso 3: Consultando transacciones recientes ---")
    recent = json.loads(recent_transactions_resource())
    print(f"   Total transacciones recientes en sistema: {len(recent)}")
    for txn in recent[:5]:
        status_icon = {"approved": "✓", "pending": "⏳", "disputed": "⚠", "declined": "✗"}.get(txn["status"], "?")
        print(f"   [{status_icon}] {txn['id']} ${txn['amount']:,.2f} — {txn['merchant']} ({txn['status']})")

    print("\n--- Paso 4: Respuesta al cliente con IA ---")
    llm_response = _call_llm(
        "Sos un agente de soporte al cliente de una billetera virtual. Respondé en español, "
        "con empatía y profesionalismo. Sé conciso.",
        "El usuario María García reportó una transacción no reconocida de $185.000 en 'Unknown Merchant XY'. "
        "Ya bloqueamos su tarjeta y creamos una disputa. Generá un mensaje de respuesta al usuario "
        "explicando la situación y los próximos pasos.",
    )
    if llm_response != "[LLM no disponible — modo mock]":
        print(f"   [Support Agent - LLM]:\n   {llm_response}")
    else:
        print("   [Support Agent - Mock] Mensaje al cliente:")
        print("   Estimada María, detectamos actividad inusual en tu cuenta y tomamos")
        print("   medidas preventivas. Tu tarjeta fue bloqueada y se inició una disputa")
        print("   por la transacción no reconocida. Recibirás una nueva tarjeta en 48-72hs.")
        print("   El reembolso se acreditará en 5-10 días hábiles.")


def financial_advisor_agent():
    print("\n" + "=" * 60)
    print("  AGENTE ASESOR FINANCIERO")
    print("  Insights personalizados de gasto")
    print("=" * 60)

    print("\n--- Paso 1: Generando insights de gasto para user-001 ---")
    insights = generate_spending_insights("user-001")
    print(f"   Período: {insights['period']}")
    print(f"   Total gastado: ${insights['total_spent']:,.2f}")
    print(f"   Tendencia: {insights['trend']}")
    print("   Desglose por categoría:")
    for cat, amount in insights["categories"].items():
        print(f"     {cat}: ${amount:,.2f}")
    print("   Consejos:")
    for tip in insights["tips"]:
        print(f"     -> {tip}")
    if insights["anomaly_alerts"]:
        print("   Alertas de anomalías:")
        for alert in insights["anomaly_alerts"]:
            print(f"     ⚠ {alert}")

    print("\n--- Paso 2: Generando insights para user-002 ---")
    insights_2 = generate_spending_insights("user-002")
    print(f"   Total gastado: ${insights_2['total_spent']:,.2f}")
    print(f"   Tendencia: {insights_2['trend']}")
    for cat, amount in insights_2["categories"].items():
        print(f"     {cat}: ${amount:,.2f}")

    print("\n--- Paso 3: Consejo financiero con IA ---")
    llm_response = _call_llm(
        "Sos un asesor financiero personal de una billetera virtual. Respondé en español, "
        "con recomendaciones prácticas y accionables.",
        f"Generá un consejo financiero personalizado basado en estos datos de gasto:\n"
        f"- Total gastado: ${insights['total_spent']:,.2f}\n"
        f"- Categorías: {json.dumps(insights['categories'], ensure_ascii=False)}\n"
        f"- Tendencia: {insights['trend']}\n"
        f"El usuario tiene un saldo disponible de $245.000 ARS. ¿Qué le recomendás?",
    )
    if llm_response != "[LLM no disponible — modo mock]":
        print(f"   [Advisor Agent - LLM]:\n   {llm_response}")
    else:
        print("   [Advisor Agent - Mock] Consejo financiero:")
        print("   1. Tu gasto en electronics es alto — considerá un plan de cuotas sin interés")
        print("   2. Configurá un ahorro automático del 10% de cada ingreso")
        print("   3. Revisá suscripciones que no uses — podrías ahorrar $2.000/mes")
        print("   4. Con tu saldo actual, un FCI money market te daría ~5% mensual")


# ==========================================
# MODO DEMO (orquestación completa)
# ==========================================

def run_client_demo():
    print("==========================================================")
    print("  BILLETERA VIRTUAL — Plataforma Fintech con MCP")
    print("  Detección de fraude + Soporte + Insights financieros")
    print("==========================================================")

    print("\n--- Inicializando base de datos ---")
    init_database()
    print("   Modelos: User, Account, Card, Transaction, FraudAlert, Dispute")
    print("   Datos de ejemplo: 3 usuarios, 3 cuentas, 4 tarjetas, 10 transacciones, 3 alertas")

    print("\n--- MCP Server registrado ---")
    print("   Herramientas: analyze_transaction, get_account_summary,")
    print("                 detect_fraud_patterns, generate_spending_insights,")
    print("                 block_suspicious_card, create_dispute")
    print("   Recursos:     transactions://recent, fraud://alerts")

    print("\n--- Escenario: Detección de fraude en tiempo real ---")
    print("   María García (user-001) tiene actividad sospechosa:")
    print("   - Dos transacciones desde Berlín en los últimos 5 minutos")
    print("   - IP conocida por actividad maliciosa (185.220.101.42)")
    print("   - Montos inusuales: $185.000 y $95.000")
    print("   - Device fingerprint nunca antes visto")

    fraud_detection_agent()
    customer_support_agent()
    financial_advisor_agent()

    print("\n" + "=" * 60)
    print("  INTEGRACIÓN MCP EN PRODUCCIÓN")
    print("=" * 60)
    print("""
  MCP habilita integración estandarizada con:

  Procesadores de pago:
    - Stripe, Adyen, dLocal, PayU → MCP tools para procesar pagos
    - Cada procesador expone su propio MCP server

  Redes bancarias:
    - SWIFT gpi, ACH, transferencias CBU/CVU
    - MCP server por cada red → tools: transfer, verify_account

  Burós de crédito:
    - Veraz, Nosis, Equifax → MCP tools: check_credit_score
    - Scoring en tiempo real durante autorización

  Compliance y KYC:
    - Jumio, Onfido, Trulioo → MCP tools: verify_identity
    - Listas OFAC/PEP screening → MCP resource: compliance://status

  Notificaciones:
    - Twilio (SMS), Firebase (push), SendGrid (email)
    - MCP tools: send_alert, notify_user

  El MCP Client (agente de IA) orquesta todos estos servidores
  de forma transparente, sin acoplamiento directo.
""")

    print("==========================================================")
    print("  Demo completada.")
    print("  Ejecutá con --serve para iniciar como servidor MCP real.")
    print("==========================================================")


# ==========================================
# MODO SERVIDOR MCP
# ==========================================

def run_server():
    init_database()
    print("Iniciando MCP Server 'virtual-wallet'...")
    print("  Transporte: stdio")
    print("  Herramientas: analyze_transaction, get_account_summary, detect_fraud_patterns,")
    print("                generate_spending_insights, block_suspicious_card, create_dispute")
    print("  Recursos: transactions://recent, fraud://alerts")
    mcp.run()


if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_server()
    else:
        run_client_demo()
