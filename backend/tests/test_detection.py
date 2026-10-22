import numpy as np, pandas as pd
from app.detection import anomaly_layer, assess, level_for, threshold_layer, thresholds_for, trend_layer

rng = np.random.default_rng(1)


def stable(n=80):
    return pd.DataFrame({"hr": 75 + rng.normal(0, 2, n), "sys": 122 + rng.normal(0, 3, n), "dia": 78 + rng.normal(0, 2, n),
                         "spo2": 97 + rng.normal(0, .3, n), "temp": 36.8 + rng.normal(0, .08, n)})


def test_stable_patient_is_low_risk():
    assert assess(stable(), ml_state={})["level"] == "stable"


def test_threshold_flags_low_spo2_as_high():
    df = stable(); df.loc[df.index[-1], "spo2"] = 85
    f = threshold_layer(df.iloc[-1].to_dict(), thresholds_for())
    assert f and f[0].severity == "high" and f[0].vital == "spo2"


def test_custom_threshold_is_respected():
    row = {"hr": 100, "sys": 120, "dia": 80, "spo2": 97, "temp": 36.8}
    assert not threshold_layer(row, thresholds_for())
    assert threshold_layer(row, thresholds_for({"hr": [50, 90]}))


def test_anomaly_detects_jump_from_baseline():
    df = stable(); df.loc[df.index[-3:], "hr"] = 115
    assert any(f.vital == "hr" for f in anomaly_layer(df))


def test_trend_detects_steady_spo2_decline():
    df = stable(); df.loc[df.index[-12:], "spo2"] = np.linspace(97, 94.5, 12)
    assert any(f.vital == "spo2" and "down" in f.message for f in trend_layer(df))


def test_levels():
    assert (level_for(0), level_for(15), level_for(40)) == ("stable", "watch", "high")
