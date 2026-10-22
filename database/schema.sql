-- CareWatch RPM database schema (PostgreSQL) + demo seed data. All data is simulated.
-- The API also creates these tables automatically on startup, so running this file is optional.

CREATE TABLE patients (
	id SERIAL NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	age INTEGER NOT NULL, 
	sex VARCHAR(1) NOT NULL, 
	condition VARCHAR(80) NOT NULL, 
	thresholds JSON, 
	risk_score INTEGER NOT NULL, 
	risk_level VARCHAR(10) NOT NULL, 
	factors JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(120) NOT NULL, 
	full_name VARCHAR(100) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE alerts (
	id BIGSERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	ts TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	layer VARCHAR(12) NOT NULL, 
	severity VARCHAR(8) NOT NULL, 
	message VARCHAR(255) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	acknowledged_by VARCHAR(50), 
	acknowledged_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
);
CREATE INDEX ix_alerts_patient_id ON alerts (patient_id);
CREATE INDEX ix_alerts_status ON alerts (status);
CREATE INDEX ix_alerts_ts ON alerts (ts);

CREATE TABLE audit_log (
	id BIGSERIAL NOT NULL, 
	user_id INTEGER, 
	username VARCHAR(50), 
	action VARCHAR(60) NOT NULL, 
	patient_id INTEGER, 
	ts TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ip VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE risk_snapshots (
	id BIGSERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	ts TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	score INTEGER NOT NULL, 
	level VARCHAR(10) NOT NULL, 
	factors JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
);
CREATE INDEX ix_risk_snapshots_patient_id ON risk_snapshots (patient_id);

CREATE TABLE vitals (
	id BIGSERIAL NOT NULL, 
	patient_id INTEGER NOT NULL, 
	ts TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	hr FLOAT NOT NULL, 
	sys FLOAT NOT NULL, 
	dia FLOAT NOT NULL, 
	spo2 FLOAT NOT NULL, 
	temp FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(patient_id) REFERENCES patients (id)
);
CREATE INDEX ix_vitals_patient_ts ON vitals (patient_id, ts);

-- Demo users (password: demo123 - change before any real use)
INSERT INTO users (username,password_hash,full_name,role,created_at) VALUES
('dr.rao','$2b$12$Ugm5ZuinNg/3ELx.n0w7w.4VYfa/d82v1hINduJ9P0TFaJfcPnJ6G','Dr. Rao','physician',NOW()),
('nurse.sen','$2b$12$Ugm5ZuinNg/3ELx.n0w7w.4VYfa/d82v1hINduJ9P0TFaJfcPnJ6G','Nurse Sen','nurse',NOW()),
('admin','$2b$12$Ugm5ZuinNg/3ELx.n0w7w.4VYfa/d82v1hINduJ9P0TFaJfcPnJ6G','Admin','admin',NOW())
ON CONFLICT (username) DO NOTHING;

INSERT INTO patients (code,name,age,sex,condition,risk_score,risk_level,factors,created_at) VALUES
('PT-01','Noah Bennett',63,'M','hypertension',0,'stable','[]',NOW()),
('PT-02','Eleanor Brooks',48,'F','hypertension',0,'stable','[]',NOW()),
('PT-03','Marcus Chen',51,'M','type 2 diabetes',0,'stable','[]',NOW()),
('PT-04','Priya Nair',67,'F','COPD',0,'stable','[]',NOW()),
('PT-05','Samuel Okafor',74,'M','atrial fibrillation',0,'stable','[]',NOW()),
('PT-06','Hana Kobayashi',58,'F','heart failure',0,'stable','[]',NOW()),
('PT-07','Lucas Ferreira',45,'M','asthma',0,'stable','[]',NOW()),
('PT-08','Ayesha Rahman',69,'F','CKD',0,'stable','[]',NOW())
ON CONFLICT (code) DO NOTHING;
