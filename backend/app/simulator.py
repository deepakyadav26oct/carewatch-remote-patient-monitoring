"""Simulated vitals. Runs inside the API (SIMULATE=true) or as a standalone client:
   python -m app.simulator --api https://your-api --key SIMULATOR_KEY [--deteriorate 3]"""
import argparse, random, time

VITALS = ("hr", "sys", "dia", "spo2", "temp")
BASE = {1: (77, 150, 92, 95, 36.8), 2: (72, 137, 86, 96, 37.0), 3: (75, 128, 80, 96, 37.1),
        4: (78, 126, 80, 95, 36.9), 5: (88, 122, 74, 96, 36.7), 6: (84, 118, 76, 96, 36.8),
        7: (70, 114, 72, 98, 36.8), 8: (80, 138, 86, 96, 37.0)}
SLOW_DRIFT = {1: {"sys": .9, "dia": .4}, 4: {"spo2": -.1, "hr": .45}, 5: {"hr": .7}}  # start after ~40 s
CRISIS = {"spo2": -.2, "hr": .8, "sys": .5, "temp": .04}
AMP = {"hr": 4, "sys": 5, "dia": 3, "spo2": .7, "temp": .15}
LIMITS = {"hr": (30, 190), "sys": (60, 220), "dia": (35, 130), "spo2": (70, 100), "temp": (34, 40.5)}
DRIFT_TICKS = 60  # a drift lasts ~90 s, then the patient slowly recovers


class Simulator:
    def __init__(self):
        self.live = 0
        self.off = {p: dict.fromkeys(VITALS, 0.0) for p in BASE}
        self.drift = {p: None for p in BASE}

    def deteriorate(self, pid: int) -> bool:
        if pid not in BASE:
            return False
        self.drift[pid] = {"rate": CRISIS, "left": DRIFT_TICKS}
        return True

    def tick(self, warmup: bool = False) -> list[dict]:
        if not warmup:
            self.live += 1
            if self.live == 26:
                for pid, rate in SLOW_DRIFT.items():
                    self.drift[pid] = {"rate": rate, "left": DRIFT_TICKS}
        out = []
        for pid, base in BASE.items():
            d = self.drift[pid]
            if d:
                for k, r in d["rate"].items():
                    self.off[pid][k] += r
                d["left"] -= 1
                if d["left"] <= 0:
                    self.drift[pid] = None
            else:
                for k in VITALS:
                    self.off[pid][k] *= 0.9  # recover towards baseline
            row = {"patient_id": pid}
            for k, b in zip(VITALS, base):
                v = b + self.off[pid][k] + (random.random() + random.random() - 1) * AMP[k]
                lo, hi = LIMITS[k]
                row[k] = round(min(hi, max(lo, v)), 1 if k in ("spo2", "temp") else 0)
            out.append(row)
        return out


if __name__ == "__main__":
    import requests
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--interval", type=float, default=1.5)
    ap.add_argument("--deteriorate", type=int, help="patient id to start declining immediately")
    a = ap.parse_args()
    sim = Simulator()
    if a.deteriorate:
        sim.deteriorate(a.deteriorate)
    while True:
        for r in sim.tick():
            try:
                requests.post(a.api.rstrip("/") + "/vitals", json=r, headers={"X-API-Key": a.key}, timeout=10)
            except requests.RequestException as e:
                print("post failed:", e)
        time.sleep(a.interval)
