-- Smart Hospital Management System - SQLite Schema
-- Converted from Oracle Review II script
-- Run order: schema.sql -> seed.sql -> triggers.sql

-- Enable foreign keys (also set per-connection in Python)
PRAGMA foreign_keys = ON;

-- ===== Domain Tables (8) =====

CREATE TABLE patient (
    patient_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name       TEXT NOT NULL,
    gender             TEXT,
    date_of_birth      TEXT NOT NULL,
    phone              TEXT NOT NULL,
    address            TEXT,
    blood_group        TEXT,
    emergency_contact  TEXT,
    registration_date  TEXT DEFAULT (date('now','localtime')),
    CONSTRAINT uq_pat_phone UNIQUE (phone),
    CONSTRAINT chk_pat_gender CHECK (gender IN ('Male','Female','Other')),
    CONSTRAINT chk_pat_phone CHECK (phone GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
    CONSTRAINT chk_pat_blood CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-'))
);

CREATE TABLE doctor (
    doctor_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_name          TEXT NOT NULL,
    department           TEXT NOT NULL,
    specialization       TEXT,
    phone                TEXT,
    consultation_fee     NUMERIC NOT NULL,
    shift                TEXT,
    availability_status  TEXT DEFAULT 'Available' NOT NULL,
    CONSTRAINT uq_doc_phone UNIQUE (phone),
    CONSTRAINT chk_doc_fee CHECK (consultation_fee > 0),
    CONSTRAINT chk_doc_shift CHECK (shift IN ('Morning','Evening','Night')),
    CONSTRAINT chk_doc_avail CHECK (availability_status IN ('Available','Busy'))
);

CREATE TABLE bed (
    bed_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ward_type     TEXT NOT NULL,
    bed_status    TEXT DEFAULT 'Free' NOT NULL,
    daily_charge  NUMERIC NOT NULL,
    CONSTRAINT chk_bed_ward CHECK (ward_type IN ('General','Private','ICU','Emergency')),
    CONSTRAINT chk_bed_stat CHECK (bed_status IN ('Free','Occupied','Cleaning')),
    CONSTRAINT chk_bed_chg CHECK (daily_charge > 0)
);

CREATE TABLE medicine (
    medicine_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_name   TEXT NOT NULL,
    manufacturer    TEXT,
    price_per_unit  NUMERIC NOT NULL,
    stock_quantity  INTEGER DEFAULT 0 NOT NULL,
    CONSTRAINT chk_med_price CHECK (price_per_unit > 0),
    CONSTRAINT chk_med_stock CHECK (stock_quantity >= 0)
);

CREATE TABLE visit (
    visit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL,
    doctor_id       INTEGER NOT NULL,
    bed_id          INTEGER,
    visit_type      TEXT NOT NULL,
    visit_datetime  TEXT NOT NULL,
    complaint       TEXT,
    triage_level    INTEGER,
    visit_status    TEXT DEFAULT 'Scheduled' NOT NULL,
    admit_time      TEXT,
    discharge_time  TEXT,
    CONSTRAINT fk_visit_patient FOREIGN KEY (patient_id) REFERENCES patient (patient_id),
    CONSTRAINT fk_visit_doctor FOREIGN KEY (doctor_id) REFERENCES doctor (doctor_id),
    CONSTRAINT fk_visit_bed FOREIGN KEY (bed_id) REFERENCES bed (bed_id),
    CONSTRAINT chk_visit_type CHECK (visit_type IN ('Appointment','Emergency')),
    CONSTRAINT chk_visit_status CHECK (visit_status IN ('Scheduled','Waiting','Under Treatment','Admitted','Discharged','Cancelled')),
    CONSTRAINT chk_visit_range CHECK (triage_level BETWEEN 1 AND 4),
    CONSTRAINT chk_visit_triage CHECK (
        (visit_type = 'Emergency' AND triage_level IS NOT NULL) OR
        (visit_type = 'Appointment' AND triage_level IS NULL)
    ),
    CONSTRAINT chk_visit_bed CHECK (visit_status <> 'Admitted' OR bed_id IS NOT NULL),
    CONSTRAINT chk_visit_disch CHECK (discharge_time >= admit_time)
);

CREATE TABLE prescription (
    prescription_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id         INTEGER NOT NULL,
    medicine_id      INTEGER NOT NULL,
    dosage           TEXT,
    duration_days    INTEGER,
    quantity         INTEGER,
    CONSTRAINT fk_presc_visit FOREIGN KEY (visit_id) REFERENCES visit (visit_id) ON DELETE CASCADE,
    CONSTRAINT fk_presc_med FOREIGN KEY (medicine_id) REFERENCES medicine (medicine_id),
    CONSTRAINT chk_presc_days CHECK (duration_days > 0),
    CONSTRAINT chk_presc_qty CHECK (quantity > 0)
);

CREATE TABLE bill (
    bill_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id             INTEGER NOT NULL,
    consultation_charge  NUMERIC DEFAULT 0 NOT NULL,
    medicine_charge      NUMERIC DEFAULT 0 NOT NULL,
    bed_charge           NUMERIC DEFAULT 0 NOT NULL,
    total_amount         NUMERIC NOT NULL,
    payment_mode         TEXT,
    payment_status       TEXT DEFAULT 'Pending' NOT NULL,
    bill_date            TEXT DEFAULT (date('now','localtime')),
    CONSTRAINT uq_bill_visit UNIQUE (visit_id),
    CONSTRAINT fk_bill_visit FOREIGN KEY (visit_id) REFERENCES visit (visit_id),
    CONSTRAINT chk_bill_mode CHECK (payment_mode IN ('Cash','Card','UPI')),
    CONSTRAINT chk_bill_stat CHECK (payment_status IN ('Paid','Pending')),
    CONSTRAINT chk_bill_amt CHECK (consultation_charge >= 0 AND medicine_charge >= 0 AND bed_charge >= 0),
    CONSTRAINT chk_bill_total CHECK (total_amount = consultation_charge + medicine_charge + bed_charge),
    CONSTRAINT chk_bill_paid CHECK (payment_status = 'Pending' OR payment_mode IS NOT NULL)
);

CREATE TABLE audit_log (
    log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name   TEXT NOT NULL,
    action_type  TEXT NOT NULL,
    record_id    INTEGER,
    changed_by   TEXT,
    change_time  TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    description  TEXT,
    CONSTRAINT chk_audit_act CHECK (action_type IN ('INSERT','UPDATE','DELETE'))
);

-- ===== Technical Tables (not part of ER diagram) =====
-- Used by triggers to know who made a change (SQLite has no USER)
CREATE TABLE app_session (
    id       INTEGER PRIMARY KEY,
    username TEXT NOT NULL
);

-- Insert default session row (username updated per request via role header)
INSERT INTO app_session (id, username) VALUES (1, 'ADMIN');

-- Password authentication & server-side session tables
CREATE TABLE IF NOT EXISTS user_account (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'Admin',
    full_name     TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now','localtime')),
    last_login    TEXT,
    CONSTRAINT chk_user_role CHECK (role IN ('Admin','Receptionist','Triage Nurse','Doctor','Billing'))
);

CREATE TABLE IF NOT EXISTS user_session (
    session_id    TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    username      TEXT NOT NULL,
    role          TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now','localtime')),
    expires_at    TEXT NOT NULL,
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES user_account (user_id) ON DELETE CASCADE
);


-- ===== Indexes =====

-- Partial unique index: prevent double-booking same doctor at same time (unless Cancelled)
CREATE UNIQUE INDEX uq_doctor_slot ON visit(doctor_id, visit_datetime) WHERE visit_status <> 'Cancelled';

-- Partial unique index: prevent two admitted patients on same bed
CREATE UNIQUE INDEX uq_active_bed ON visit(bed_id) WHERE visit_status = 'Admitted';

-- Regular indexes for query performance
CREATE INDEX idx_visit_patient ON visit(patient_id);
CREATE INDEX idx_visit_doctor ON visit(doctor_id);
CREATE INDEX idx_presc_visit ON prescription(visit_id);