import os
from sqlalchemy.orm import Session
from .auth import hash_pw
from .models import Patient, User

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo123")
USERS = [("dr.rao", "Dr. Rao", "physician"), ("nurse.sen", "Nurse Sen", "nurse"), ("admin", "Admin", "admin")]
PATIENTS = [("PT-01", "Noah Bennett", 63, "M", "hypertension"), ("PT-02", "Eleanor Brooks", 48, "F", "hypertension"),
            ("PT-03", "Marcus Chen", 51, "M", "type 2 diabetes"), ("PT-04", "Priya Nair", 67, "F", "COPD"),
            ("PT-05", "Samuel Okafor", 74, "M", "atrial fibrillation"), ("PT-06", "Hana Kobayashi", 58, "F", "heart failure"),
            ("PT-07", "Lucas Ferreira", 45, "M", "asthma"), ("PT-08", "Ayesha Rahman", 69, "F", "CKD")]


def seed(db: Session):
    if db.query(User).count() == 0:
        pw = hash_pw(DEMO_PASSWORD)
        db.add_all(User(username=u, password_hash=pw, full_name=n, role=r) for u, n, r in USERS)
    if db.query(Patient).count() == 0:
        db.add_all(Patient(code=c, name=n, age=a, sex=s, condition=cd) for c, n, a, s, cd in PATIENTS)
    db.commit()
