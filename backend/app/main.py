"""CareWatch RPM API. Simulated data only - decision support, not a medical device."""
import asyncio, os, secrets, threading, time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import timedelta

import jwt
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import current_user, decode_token, make_token, require_role, verify_pw
from .database import Base, SessionLocal, engine, get_db
from .detection import VITALS, assess, thresholds_for
from .models import Alert, AuditLog, Patient, RiskSnapshot, User, Vital, iso, utcnow
from .seed import seed
from .simulator import Simulator
from .ws import manager

DISCLAIMER = "Simulated data. Decision support only; not a medical device and not a diagnosis."
SIMULATOR_KEY = os.getenv("SIMULATOR_KEY", "dev-simulator-key")
SIMULATE = os.getenv("SIMULATE", "true").lower() == "true"
RETAIN_HOURS = int(os.getenv("RETAIN_HOURS", "24"))
ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONTEND_URL", "*").split(",") if o.strip()]

HIST: dict[int, deque] = {}   # last 120 readings per patient (detection window)
ML: dict[int, dict] = {}      # per-patient Isolation Forest state
COOL: dict[tuple, object] = {}
LOCK = threading.Lock()
FAILS: dict[str, list] = defaultdict(list)


class VitalIn(BaseModel):
    patient_id: int
    hr: float = Field(ge=20, le=250)
    sys: float = Field(ge=50, le=260)
    dia: float = Field(ge=30, le=160)
    spo2: float = Field(ge=50, le=100)
    temp: float = Field(ge=33, le=42)


def audit(db: Session, user: User | None, action: str, pid: int | None = None, ip: str | None = None):
    db.add(AuditLog(user_id=user.id if user else None, username=user.username if user else None,
                    action=action, patient_id=pid, ip=ip))


def alert_dict(a: Alert, name: str) -> dict:
    return {"id": a.id, "patient_id": a.patient_id, "patient_name": name, "ts": iso(a.ts), "layer": a.layer,
            "severity": a.severity, "message": a.message, "status": a.status}


def vital_dict(v: Vital) -> dict:
    return {"ts": iso(v.ts), **{k: getattr(v, k) for k in VITALS}}


def process(data: dict) -> dict:
    """Store one reading, run detection, save new alerts. Used by POST /vitals and the built-in simulator."""
    with LOCK, SessionLocal() as db:
        pid = data["patient_id"]
        p = db.get(Patient, pid)
        if not p:
            raise KeyError(pid)
        reading = {k: float(data[k]) for k in VITALS}
        db.add(Vital(patient_id=pid, **reading))
        if pid not in HIST:
            rows = (db.query(Vital).filter(Vital.patient_id == pid).order_by(Vital.id.desc()).limit(120).all())
            HIST[pid] = deque([{k: getattr(r, k) for k in VITALS} for r in reversed(rows)], maxlen=120)
        HIST[pid].append(reading)
        res = assess(pd.DataFrame(HIST[pid]), thresholds_for(p.thresholds), ML.setdefault(pid, {}))
        now, new = utcnow(), []
        for f in res["findings"]:
            key = (pid, f.layer, f.vital)
            if key in COOL and (now - COOL[key]).total_seconds() < 60:
                continue
            COOL[key] = now
            a = Alert(patient_id=pid, ts=now, layer=f.layer, severity=f.severity, message=f.message[:255])
            db.add(a)
            new.append(a)
        if res["level"] == "stable":  # auto-resolve alerts older than 60 s once readings are back to normal
            db.query(Alert).filter(Alert.patient_id == pid, Alert.status == "active",
                                   Alert.ts < now - timedelta(seconds=60)).update({"status": "resolved"})
        if res["level"] != p.risk_level:
            db.add(RiskSnapshot(patient_id=pid, score=res["score"], level=res["level"], factors=res["factors"]))
        p.risk_score, p.risk_level, p.factors = res["score"], res["level"], res["factors"]
        db.commit()
        return {"type": "reading", "patient_id": pid, "vital": reading,
                "risk": {"score": res["score"], "level": res["level"], "factors": res["factors"]},
                "alerts": [alert_dict(a, p.name) for a in new]}


async def sim_loop(sim: Simulator, have: int):
    for _ in range(max(0, 60 - have)):  # warm-up so detection has a baseline (runs in background, API stays responsive)
        for r in sim.tick(warmup=True):
            await asyncio.to_thread(process, r)
    while True:
        for r in sim.tick():
            msg = await asyncio.to_thread(process, r)
            await manager.broadcast(msg)
        await asyncio.sleep(1.5)


async def cleanup_loop():
    while True:
        await asyncio.sleep(600)
        with SessionLocal() as db:
            db.query(Vital).filter(Vital.ts < utcnow() - timedelta(hours=RETAIN_HOURS)).delete()
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
        have = db.query(Vital).filter(Vital.patient_id == 1).count()
    tasks = [asyncio.create_task(cleanup_loop())]
    app.state.sim = None
    if SIMULATE:
        sim = app.state.sim = Simulator()
        tasks.append(asyncio.create_task(sim_loop(sim, have)))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="CareWatch RPM API", version="1.0", description=DISCLAIMER, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def disclaimer_header(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Disclaimer"] = DISCLAIMER
    return resp


@app.get("/health")
def health():
    return {"ok": True, "simulator": SIMULATE, "disclaimer": DISCLAIMER}


@app.post("/auth/login")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "?"
    now = time.time()
    FAILS[ip] = [t for t in FAILS[ip] if now - t < 60]
    if len(FAILS[ip]) >= 10:
        raise HTTPException(429, "Too many failed attempts. Try again in a minute.")
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_pw(form.password, user.password_hash):
        FAILS[ip].append(now)
        raise HTTPException(401, "Invalid credentials")
    audit(db, user, "login", ip=ip)
    db.commit()
    return {"access_token": make_token(user), "token_type": "bearer",
            "user": {"username": user.username, "full_name": user.full_name, "role": user.role}}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"username": user.username, "full_name": user.full_name, "role": user.role}


def latest_vital(db: Session, pid: int):
    if HIST.get(pid):
        return dict(HIST[pid][-1])
    v = db.query(Vital).filter(Vital.patient_id == pid).order_by(Vital.id.desc()).first()
    return {k: getattr(v, k) for k in VITALS} if v else None


def patient_dict(p: Patient) -> dict:
    return {"id": p.id, "code": p.code, "name": p.name, "age": p.age, "sex": p.sex, "condition": p.condition}


@app.get("/patients")
def patients(user: User = Depends(current_user), db: Session = Depends(get_db)):
    active = dict(db.query(Alert.patient_id, func.count()).filter(Alert.status == "active")
                  .group_by(Alert.patient_id).all())
    return [{**patient_dict(p), "latest": latest_vital(db, p.id),
             "risk": {"score": p.risk_score, "level": p.risk_level, "factors": p.factors or []},
             "active_alerts": active.get(p.id, 0)} for p in db.query(Patient).order_by(Patient.id)]


@app.get("/patients/{pid}")
def patient(pid: int, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Patient, pid)
    if not p:
        raise HTTPException(404, "Patient not found")
    audit(db, user, "view_patient", pid, request.client.host if request.client else None)
    db.commit()
    return {**patient_dict(p), "thresholds": thresholds_for(p.thresholds), "latest": latest_vital(db, pid),
            "risk": {"score": p.risk_score, "level": p.risk_level, "factors": p.factors or []}}


@app.get("/patients/{pid}/vitals")
def patient_vitals(pid: int, hours: float = Query(6, gt=0, le=72), limit: int = Query(300, ge=1, le=2000),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(hours=hours)
    rows = (db.query(Vital).filter(Vital.patient_id == pid, Vital.ts >= since)
            .order_by(Vital.id.desc()).limit(limit).all())
    return [vital_dict(v) for v in reversed(rows)]


@app.post("/vitals")
async def ingest(v: VitalIn, x_api_key: str | None = Header(None)):
    if not x_api_key or not secrets.compare_digest(x_api_key, SIMULATOR_KEY):
        raise HTTPException(401, "Missing or invalid simulator API key")
    try:
        msg = await asyncio.to_thread(process, v.model_dump())
    except KeyError:
        raise HTTPException(404, "Unknown patient")
    await manager.broadcast(msg)
    return {"risk": msg["risk"], "new_alerts": len(msg["alerts"]), "disclaimer": DISCLAIMER}


@app.get("/alerts")
def alerts(status: str | None = None, severity: str | None = None, patient_id: int | None = None,
           limit: int = Query(80, ge=1, le=500), user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Alert, Patient.name).join(Patient, Patient.id == Alert.patient_id)
    if status:
        q = q.filter(Alert.status == status)
    if severity:
        q = q.filter(Alert.severity == severity)
    if patient_id:
        q = q.filter(Alert.patient_id == patient_id)
    return [alert_dict(a, n) for a, n in q.order_by(Alert.id.desc()).limit(limit).all()]


@app.post("/alerts/{aid}/acknowledge")
def acknowledge(aid: int, request: Request, user: User = Depends(require_role("physician", "admin")),
                db: Session = Depends(get_db)):
    a = db.get(Alert, aid)
    if not a:
        raise HTTPException(404, "Alert not found")
    if a.status != "acknowledged":
        a.status, a.acknowledged_by, a.acknowledged_at = "acknowledged", user.username, utcnow()
        audit(db, user, "acknowledge_alert", a.patient_id, request.client.host if request.client else None)
        db.commit()
    return {"id": a.id, "status": a.status, "acknowledged_by": a.acknowledged_by}


@app.get("/model/stats")
def model_stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    by_layer = dict(db.query(Alert.layer, func.count()).group_by(Alert.layer).all())
    return {"readings_processed": db.query(Vital).count() * len(VITALS),
            "alerts_total": sum(by_layer.values()), "alerts_by_layer": by_layer,
            "active_alerts": db.query(Alert).filter(Alert.status == "active").count(),
            "layers": ["threshold", "anomaly", "trend", "ml"], "disclaimer": DISCLAIMER}


@app.post("/simulate/deteriorate/{pid}")
def deteriorate(pid: int, user: User = Depends(require_role("physician", "admin"))):
    sim = app.state.sim
    if sim is None:
        raise HTTPException(409, "Built-in simulator is disabled (SIMULATE=false)")
    if not sim.deteriorate(pid):
        raise HTTPException(404, "Unknown patient")
    return {"ok": True, "patient_id": pid}


@app.websocket("/ws/live")
async def live(ws: WebSocket, token: str = ""):
    try:
        decode_token(token)
    except jwt.PyJWTError:
        await ws.close(code=4401)
        return
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
