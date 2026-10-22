"""Detection engine: four independent layers combined into a 0-100 risk score.
Decision support only - it flags readings for clinical review, never diagnoses."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

VITALS = ("hr", "sys", "dia", "spo2", "temp")
DEFAULTS = {"hr": (50, 110), "sys": (90, 160), "dia": (55, 100), "spo2": (93, 101), "temp": (35.8, 38.0)}
LABEL = {"hr": "Heart rate", "sys": "Systolic BP", "dia": "Diastolic BP", "spo2": "SpO₂", "temp": "Temperature"}
UNIT = {"hr": "bpm", "sys": "mmHg", "dia": "mmHg", "spo2": "%", "temp": "°C"}
SLOPE_LIMIT = {"hr": 0.6, "sys": 0.9, "dia": 0.5, "spo2": 0.08, "temp": 0.03}


@dataclass
class Finding:
    layer: str      # threshold | anomaly | trend | ml
    vital: str
    severity: str   # watch | high
    message: str
    points: int


def fmt(k: str, v: float) -> str:
    return f"{v:.1f}" if k in ("spo2", "temp") else f"{v:.0f}"


def thresholds_for(custom: dict | None = None) -> dict:
    th = {k: tuple(v) for k, v in DEFAULTS.items()}
    for k, v in (custom or {}).items():
        if k in th:
            th[k] = (float(v[0]), float(v[1]))
    return th


def threshold_layer(row: dict, th: dict) -> list[Finding]:
    out = []
    for k in VITALS:
        v, (lo, hi) = row[k], th[k]
        if v < lo or v > hi:
            pts = 30 if (k == "spo2" and v < 90) or v > hi * 1.15 else 25 if k == "spo2" else 18
            out.append(Finding("threshold", k, "high" if pts >= 25 else "watch",
                               f"{LABEL[k]} {fmt(k, v)} {UNIT[k]} outside {lo:g}–{hi:g}", pts))
    return out


def anomaly_layer(df: pd.DataFrame) -> list[Finding]:
    """Last 3 readings vs the patient's own previous 35 (z-score)."""
    if len(df) < 40:
        return []
    out = []
    for k in VITALS:
        base = df[k].iloc[-40:-5]
        sd = base.std(ddof=0)
        sd = sd if sd and sd > 1e-6 else 1.0
        z = (df[k].iloc[-3:].mean() - base.mean()) / sd
        if abs(z) > 3:
            out.append(Finding("anomaly", k, "watch", f"{LABEL[k]} deviates {z:.1f}σ from personal baseline", 12))
    return out


def trend_layer(df: pd.DataFrame) -> list[Finding]:
    """Slope of a straight line fitted to the last 12 readings."""
    if len(df) < 12:
        return []
    out, x = [], np.arange(12)
    for k in VITALS:
        s = float(np.polyfit(x, df[k].iloc[-12:].to_numpy(float), 1)[0])
        if abs(s) > SLOPE_LIMIT[k] and (k != "spo2" or s < 0):
            out.append(Finding("trend", k, "watch",
                               f"{LABEL[k]} trending {'up' if s > 0 else 'down'} ({s:.2f}/reading)", 10))
    return out


def ml_layer(df: pd.DataFrame, state: dict) -> list[Finding]:
    """Per-patient Isolation Forest on a rolling window; retrained every 30 readings."""
    if len(df) < 60:
        return []
    X = df[list(VITALS)].to_numpy(float)
    state["n"] = state.get("n", 0) + 1
    if state.get("model") is None or state["n"] % 30 == 0:
        state["model"] = IsolationForest(n_estimators=100, contamination=0.01, random_state=0).fit(X[:-3])
    score = float(state["model"].decision_function(X[-3:]).mean())
    if score < -0.08:
        return [Finding("ml", "all", "watch", f"Isolation Forest: unusual combination of vitals (score {score:.2f})", 10)]
    return []


def level_for(score: int) -> str:
    return "high" if score >= 40 else "watch" if score >= 15 else "stable"


def assess(df: pd.DataFrame, th: dict | None = None, ml_state: dict | None = None) -> dict:
    th = th or thresholds_for()
    ml_state = ml_state if ml_state is not None else {}
    findings = (threshold_layer(df.iloc[-1].to_dict(), th) + anomaly_layer(df)
                + trend_layer(df) + ml_layer(df, ml_state))
    score = min(100, sum(f.points for f in findings))
    return {"score": score, "level": level_for(score), "factors": [f.message for f in findings], "findings": findings}
