-- =============================================================================
-- Smart Hospital Management System — Supabase PostgreSQL Schema & Seed
-- Converted from Review II Specification
-- =============================================================================

-- Drop tables if resetting (with CASCADE)
DROP TABLE IF EXISTS user_session CASCADE;
DROP TABLE IF EXISTS user_account CASCADE;
DROP TABLE IF EXISTS app_session CASCADE;
DROP TABLE IF EXISTS bill CASCADE;
DROP TABLE IF EXISTS prescription CASCADE;
DROP TABLE IF EXISTS visit CASCADE;
DROP TABLE IF EXISTS medicine CASCADE;
DROP TABLE IF EXISTS bed CASCADE;
DROP TABLE IF EXISTS doctor CASCADE;
DROP TABLE IF EXISTS patient CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;

-- ===== Domain Tables (8) =====

CREATE TABLE patient (
    patient_id         SERIAL PRIMARY KEY,
    patient_name       VARCHAR(100) NOT NULL,
    gender             VARCHAR(10),
    date_of_birth      DATE NOT NULL,
    phone              VARCHAR(15) NOT NULL,
    address            TEXT,
    blood_group        VARCHAR(5),
    emergency_contact  VARCHAR(15),
    registration_date  DATE DEFAULT CURRENT_DATE,
    CONSTRAINT uq_pat_phone UNIQUE (phone),
    CONSTRAINT chk_pat_gender CHECK (gender IN ('Male','Female','Other')),
    CONSTRAINT chk_pat_phone CHECK (phone ~ '^[0-9]{10}$'),
    CONSTRAINT chk_pat_blood CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-'))
);

CREATE TABLE doctor (
    doctor_id            SERIAL PRIMARY KEY,
    doctor_name          VARCHAR(100) NOT NULL,
    department           VARCHAR(50) NOT NULL,
    specialization       VARCHAR(50),
    phone                VARCHAR(15),
    consultation_fee     NUMERIC(10,2) NOT NULL,
    shift                VARCHAR(10),
    availability_status  VARCHAR(15) DEFAULT 'Available' NOT NULL,
    CONSTRAINT uq_doc_phone UNIQUE (phone),
    CONSTRAINT chk_doc_fee CHECK (consultation_fee > 0),
    CONSTRAINT chk_doc_shift CHECK (shift IN ('Morning','Evening','Night')),
    CONSTRAINT chk_doc_avail CHECK (availability_status IN ('Available','Busy'))
);

CREATE TABLE bed (
    bed_id        SERIAL PRIMARY KEY,
    ward_type     VARCHAR(20) NOT NULL,
    bed_status    VARCHAR(20) DEFAULT 'Free' NOT NULL,
    daily_charge  NUMERIC(10,2) NOT NULL,
    CONSTRAINT chk_bed_ward CHECK (ward_type IN ('General','Private','ICU','Emergency')),
    CONSTRAINT chk_bed_stat CHECK (bed_status IN ('Free','Occupied','Cleaning')),
    CONSTRAINT chk_bed_chg CHECK (daily_charge > 0)
);

CREATE TABLE medicine (
    medicine_id     SERIAL PRIMARY KEY,
    medicine_name   VARCHAR(100) NOT NULL,
    manufacturer    VARCHAR(100),
    price_per_unit  NUMERIC(10,2) NOT NULL,
    stock_quantity  INTEGER DEFAULT 0 NOT NULL,
    CONSTRAINT chk_med_price CHECK (price_per_unit > 0),
    CONSTRAINT chk_med_stock CHECK (stock_quantity >= 0)
);

CREATE TABLE visit (
    visit_id        SERIAL PRIMARY KEY,
    patient_id      INTEGER NOT NULL REFERENCES patient(patient_id),
    doctor_id       INTEGER NOT NULL REFERENCES doctor(doctor_id),
    bed_id          INTEGER REFERENCES bed(bed_id),
    visit_type      VARCHAR(20) NOT NULL,
    visit_datetime  TIMESTAMP NOT NULL,
    complaint       TEXT,
    triage_level    INTEGER,
    visit_status    VARCHAR(30) DEFAULT 'Scheduled' NOT NULL,
    admit_time      TIMESTAMP,
    discharge_time  TIMESTAMP,
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
    prescription_id  SERIAL PRIMARY KEY,
    visit_id         INTEGER NOT NULL REFERENCES visit(visit_id) ON DELETE CASCADE,
    medicine_id      INTEGER NOT NULL REFERENCES medicine(medicine_id),
    dosage           VARCHAR(50),
    duration_days    INTEGER,
    quantity         INTEGER,
    CONSTRAINT chk_presc_days CHECK (duration_days > 0),
    CONSTRAINT chk_presc_qty CHECK (quantity > 0)
);

CREATE TABLE bill (
    bill_id              SERIAL PRIMARY KEY,
    visit_id             INTEGER NOT NULL UNIQUE REFERENCES visit(visit_id),
    consultation_charge  NUMERIC(10,2) DEFAULT 0 NOT NULL,
    medicine_charge      NUMERIC(10,2) DEFAULT 0 NOT NULL,
    bed_charge           NUMERIC(10,2) DEFAULT 0 NOT NULL,
    total_amount         NUMERIC(10,2) NOT NULL,
    payment_mode         VARCHAR(20),
    payment_status       VARCHAR(20) DEFAULT 'Pending' NOT NULL,
    bill_date            DATE DEFAULT CURRENT_DATE,
    CONSTRAINT chk_bill_mode CHECK (payment_mode IN ('Cash','Card','UPI')),
    CONSTRAINT chk_bill_stat CHECK (payment_status IN ('Paid','Pending')),
    CONSTRAINT chk_bill_amt CHECK (consultation_charge >= 0 AND medicine_charge >= 0 AND bed_charge >= 0),
    CONSTRAINT chk_bill_total CHECK (total_amount = consultation_charge + medicine_charge + bed_charge),
    CONSTRAINT chk_bill_paid CHECK (payment_status = 'Pending' OR payment_mode IS NOT NULL)
);

CREATE TABLE audit_log (
    log_id       SERIAL PRIMARY KEY,
    table_name   VARCHAR(50) NOT NULL,
    action_type  VARCHAR(10) NOT NULL,
    record_id    INTEGER,
    changed_by   VARCHAR(50),
    change_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description  TEXT,
    CONSTRAINT chk_audit_act CHECK (action_type IN ('INSERT','UPDATE','DELETE'))
);

-- ===== Technical Tables =====

CREATE TABLE app_session (
    id       INTEGER PRIMARY KEY,
    username VARCHAR(50) NOT NULL
);
INSERT INTO app_session (id, username) VALUES (1, 'ADMIN') ON CONFLICT (id) DO NOTHING;

CREATE TABLE user_account (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(50) NOT NULL DEFAULT 'Admin',
    full_name     VARCHAR(100),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login    TIMESTAMP,
    CONSTRAINT chk_user_role CHECK (role IN ('Admin','Receptionist','Triage Nurse','Doctor','Billing'))
);

CREATE TABLE user_session (
    session_id    VARCHAR(128) PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES user_account (user_id) ON DELETE CASCADE,
    username      VARCHAR(50) NOT NULL,
    role          VARCHAR(50) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP NOT NULL
);

-- ===== Indexes =====

CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_slot ON visit(doctor_id, visit_datetime) WHERE visit_status <> 'Cancelled';
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_bed ON visit(bed_id) WHERE visit_status = 'Admitted';
CREATE INDEX IF NOT EXISTS idx_visit_patient ON visit(patient_id);
CREATE INDEX IF NOT EXISTS idx_visit_doctor ON visit(doctor_id);
CREATE INDEX IF NOT EXISTS idx_presc_visit ON prescription(visit_id);
CREATE INDEX IF NOT EXISTS idx_session_user ON user_session(user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires ON user_session(expires_at);

-- ===== User-Defined Functions (PL/pgSQL) =====

CREATE OR REPLACE FUNCTION fn_triage_label(p_level INT)
RETURNS TEXT AS $$
BEGIN
    RETURN CASE p_level
        WHEN 1 THEN 'Critical'
        WHEN 2 THEN 'Very urgent'
        WHEN 3 THEN 'Urgent'
        WHEN 4 THEN 'Minor'
        ELSE 'Not triaged'
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION fn_medicine_cost(p_visit_id INT)
RETURNS NUMERIC AS $$
DECLARE
    v_cost NUMERIC;
BEGIN
    SELECT COALESCE(SUM(p.quantity * m.price_per_unit), 0)
    INTO v_cost
    FROM prescription p
    JOIN medicine m ON m.medicine_id = p.medicine_id
    WHERE p.visit_id = p_visit_id;
    RETURN v_cost;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION fn_days_stayed(p_visit_id INT)
RETURNS INT AS $$
DECLARE
    v_admit TIMESTAMP;
    v_discharge TIMESTAMP;
    v_days INT;
BEGIN
    SELECT admit_time, discharge_time INTO v_admit, v_discharge FROM visit WHERE visit_id = p_visit_id;
    IF v_admit IS NULL THEN
        RETURN 0;
    END IF;
    IF v_discharge IS NULL THEN
        v_discharge := CURRENT_TIMESTAMP;
    END IF;
    v_days := GREATEST(DATE_PART('day', v_discharge - v_admit)::INT, 1);
    RETURN v_days;
END;
$$ LANGUAGE plpgsql STABLE;

-- ===== Triggers & Functions =====

-- 1. Reduce / restore stock on prescription changes
CREATE OR REPLACE FUNCTION fn_reduce_stock() RETURNS TRIGGER AS $$
DECLARE
    v_stock INT;
    v_name VARCHAR(100);
BEGIN
    SELECT stock_quantity, medicine_name INTO v_stock, v_name FROM medicine WHERE medicine_id = NEW.medicine_id;
    IF v_stock < NEW.quantity THEN
        RAISE EXCEPTION 'Insufficient stock for %: available %, requested %', v_name, v_stock, NEW.quantity;
    END IF;
    UPDATE medicine SET stock_quantity = stock_quantity - NEW.quantity WHERE medicine_id = NEW.medicine_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reduce_stock__insert
BEFORE INSERT ON prescription
FOR EACH ROW EXECUTE FUNCTION fn_reduce_stock();

CREATE OR REPLACE FUNCTION fn_restore_stock() RETURNS TRIGGER AS $$
BEGIN
    UPDATE medicine SET stock_quantity = stock_quantity + OLD.quantity WHERE medicine_id = OLD.medicine_id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reduce_stock__delete
AFTER DELETE ON prescription
FOR EACH ROW EXECUTE FUNCTION fn_restore_stock();

-- 2. Audit Visit
CREATE OR REPLACE FUNCTION fn_audit_visit() RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR(50);
BEGIN
    SELECT username INTO v_user FROM app_session WHERE id = 1;
    IF v_user IS NULL THEN v_user := 'SYSTEM'; END IF;
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('VISIT', 'INSERT', NEW.visit_id, v_user, 'New ' || NEW.visit_type || ' visit for patient ' || NEW.patient_id);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('VISIT', 'UPDATE', NEW.visit_id, v_user, 'Status ' || OLD.visit_status || ' -> ' || NEW.visit_status);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('VISIT', 'DELETE', OLD.visit_id, v_user, 'Visit deleted (patient ' || OLD.patient_id || ')');
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_visit
AFTER INSERT OR UPDATE OR DELETE ON visit
FOR EACH ROW EXECUTE FUNCTION fn_audit_visit();

-- 3. Audit Bill
CREATE OR REPLACE FUNCTION fn_audit_bill() RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR(50);
BEGIN
    SELECT username INTO v_user FROM app_session WHERE id = 1;
    IF v_user IS NULL THEN v_user := 'SYSTEM'; END IF;
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('BILL', 'INSERT', NEW.bill_id, v_user, 'Bill generated: total ' || NEW.total_amount || ' (' || NEW.payment_status || ')');
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('BILL', 'UPDATE', NEW.bill_id, v_user, 'Payment status ' || OLD.payment_status || ' -> ' || NEW.payment_status);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('BILL', 'DELETE', OLD.bill_id, v_user, 'Bill deleted');
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_bill
AFTER INSERT OR UPDATE OR DELETE ON bill
FOR EACH ROW EXECUTE FUNCTION fn_audit_bill();

-- 4. Audit Patient
CREATE OR REPLACE FUNCTION fn_audit_patient() RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR(50);
BEGIN
    SELECT username INTO v_user FROM app_session WHERE id = 1;
    IF v_user IS NULL THEN v_user := 'SYSTEM'; END IF;
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('PATIENT', 'INSERT', NEW.patient_id, v_user, 'New patient registered');
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('PATIENT', 'UPDATE', NEW.patient_id, v_user, 'Patient details updated');
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
        VALUES ('PATIENT', 'DELETE', OLD.patient_id, v_user, 'Patient record deleted');
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_patient
AFTER INSERT OR UPDATE OR DELETE ON patient
FOR EACH ROW EXECUTE FUNCTION fn_audit_patient();

-- 5. Doctor Status
CREATE OR REPLACE FUNCTION fn_doctor_status() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.visit_status = 'Under Treatment' THEN
            UPDATE doctor SET availability_status = 'Busy' WHERE doctor_id = NEW.doctor_id;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.visit_status = 'Under Treatment' THEN
            UPDATE doctor SET availability_status = 'Busy' WHERE doctor_id = NEW.doctor_id;
        ELSIF OLD.visit_status = 'Under Treatment' AND NEW.visit_status <> 'Under Treatment' THEN
            UPDATE doctor SET availability_status = 'Available' WHERE doctor_id = NEW.doctor_id;
        END IF;
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_doctor_status
AFTER INSERT OR UPDATE OF visit_status ON visit
FOR EACH ROW EXECUTE FUNCTION fn_doctor_status();

-- 6. Protect Audit Log
CREATE OR REPLACE FUNCTION fn_protect_audit() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'AUDIT_LOG entries cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_audit
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION fn_protect_audit();

-- =============================================================================
-- Golden Seed Data
-- =============================================================================

-- Disable audit triggers temporarily during seeding
ALTER TABLE patient DISABLE TRIGGER trg_audit_patient;
ALTER TABLE visit DISABLE TRIGGER trg_audit_visit;
ALTER TABLE visit DISABLE TRIGGER trg_doctor_status;
ALTER TABLE bill DISABLE TRIGGER trg_audit_bill;

-- Patients (12 rows)
INSERT INTO patient (patient_id, patient_name, gender, date_of_birth, phone, address, blood_group, emergency_contact, registration_date) VALUES
(101, 'Arjun Reddy', 'Male', '1985-03-14', '9876500101', '12 Gandhi Road, Chennai', 'B+', '9876511101', '2026-01-10'),
(102, 'Kavita Sharma', 'Female', '1972-07-22', '9876500102', '45 MG Road, Bengaluru', 'O+', '9876511102', '2026-01-18'),
(103, 'Rahul Verma', 'Male', '1990-11-05', '9876500103', '7 Lake View, Hyderabad', 'A+', '9876511103', '2026-02-02'),
(104, 'Divya Krishnan', 'Female', '1998-01-30', '9876500104', '23 Anna Nagar, Chennai', 'AB+', '9876511104', '2026-02-14'),
(105, 'Mohammed Irfan', 'Male', '2018-05-19', '9876500105', '18 Park Street, Kolkata', 'O-', '9876511105', '2026-03-05'),
(106, 'Sunita Patil', 'Female', '1965-09-09', '9876500106', '5 FC Road, Pune', 'B-', '9876511106', '2026-03-21'),
(107, 'Aakash Gupta', 'Male', '2001-12-12', '9876500107', '88 Civil Lines, Delhi', 'A-', '9876511107', '2026-04-11'),
(108, 'Lakshmi Narayanan', 'Female', '1958-02-27', '9876500108', '9 Temple Street, Madurai', 'O+', '9876511108', '2026-05-02'),
(109, 'Vivek Joshi', 'Male', '1979-06-18', '9876500109', '31 Residency Road, Bengaluru', 'B+', '9876511109', '2026-06-15'),
(110, 'Neha Kapoor', 'Female', '1988-04-03', '9876500110', '14 Sector 21, Noida', 'A+', '9876511110', '2026-07-08'),
(111, 'Imran Khan', 'Male', '1995-08-25', '9876500111', '2 Mount Road, Chennai', 'AB-', '9876511111', '2026-09-14'),
(112, 'Pooja Menon', 'Female', '1993-12-01', '9876500112', '6 Marine Drive, Kochi', 'O+', '9876511112', '2026-09-15');

-- Doctors (10 rows)
INSERT INTO doctor (doctor_id, doctor_name, department, specialization, phone, consultation_fee, shift, availability_status) VALUES
(201, 'Dr. Rajesh Kumar', 'Cardiology', 'Cardiologist', '9840011101', 800, 'Morning', 'Available'),
(202, 'Dr. Priya Nair', 'General Medicine', 'Physician', '9840011102', 500, 'Morning', 'Available'),
(203, 'Dr. Arvind Menon', 'Emergency', 'Emergency Physician', '9840011103', 1000, 'Night', 'Available'),
(204, 'Dr. Sneha Iyer', 'Orthopedics', 'Orthopedic Surgeon', '9840011104', 700, 'Evening', 'Available'),
(205, 'Dr. Karthik Raman', 'Neurology', 'Neurologist', '9840011105', 900, 'Morning', 'Available'),
(206, 'Dr. Fatima Sheikh', 'Pediatrics', 'Pediatrician', '9840011106', 600, 'Morning', 'Available'),
(207, 'Dr. Vikram Singh', 'Emergency', 'Trauma Specialist', '9840011107', 1000, 'Evening', 'Busy'),
(208, 'Dr. Meena Pillai', 'Gynecology', 'Gynecologist', '9840011108', 750, 'Evening', 'Available'),
(209, 'Dr. Suresh Babu', 'General Medicine', 'Physician', '9840011109', 500, 'Evening', 'Available'),
(210, 'Dr. Anita Desai', 'Dermatology', 'Dermatologist', '9840011110', 550, 'Morning', 'Available');

-- Beds (12 rows)
INSERT INTO bed (bed_id, ward_type, bed_status, daily_charge) VALUES
(301, 'General', 'Free', 600),
(302, 'General', 'Free', 600),
(303, 'General', 'Free', 600),
(304, 'General', 'Cleaning', 600),
(305, 'Private', 'Occupied', 2500),
(306, 'Private', 'Free', 2500),
(307, 'ICU', 'Free', 5000),
(308, 'ICU', 'Occupied', 5000),
(309, 'Emergency', 'Free', 1500),
(310, 'Emergency', 'Free', 1500),
(311, 'Emergency', 'Free', 1500),
(312, 'Emergency', 'Cleaning', 1500);

-- Medicines (12 rows)
INSERT INTO medicine (medicine_id, medicine_name, manufacturer, price_per_unit, stock_quantity) VALUES
(501, 'Paracetamol 500mg', 'Cipla', 2.50, 500),
(502, 'Amoxicillin 500mg', 'Sun Pharma', 8.00, 200),
(503, 'Atorvastatin 10mg', 'Dr. Reddys', 12.00, 150),
(504, 'Metformin 500mg', 'Cipla', 4.00, 300),
(505, 'Pantoprazole 40mg', 'Alkem', 9.50, 180),
(506, 'Ceftriaxone 1g Inj', 'Torrent', 85.00, 50),
(507, 'Tramadol 50mg', 'Zydus', 15.00, 80),
(508, 'Azithromycin 500mg', 'Lupin', 22.00, 120),
(509, 'Amlodipine 5mg', 'Sun Pharma', 5.00, 250),
(510, 'Ondansetron 4mg', 'GlaxoSmithKline', 7.50, 90),
(511, 'Insulin Glargine', 'Sanofi', 450.00, 25),
(512, 'Salbutamol Inhaler', 'Cipla', 120.00, 40);

-- Visits (20 rows)
INSERT INTO visit (visit_id, patient_id, doctor_id, bed_id, visit_type, visit_datetime, complaint, triage_level, visit_status, admit_time, discharge_time) VALUES
(401, 101, 201, 305, 'Appointment', '2026-09-01 10:00:00', 'Chest pain on exertion', NULL, 'Discharged', '2026-09-01 11:00:00', '2026-09-04 16:00:00'),
(402, 102, 209, NULL, 'Appointment', '2026-09-03 11:30:00', 'Persistent cough and fever', NULL, 'Discharged', NULL, NULL),
(403, 103, 205, 308, 'Emergency', '2026-09-05 02:15:00', 'Sudden loss of consciousness', 1, 'Discharged', '2026-09-05 03:00:00', '2026-09-10 12:00:00'),
(404, 104, 204, NULL, 'Appointment', '2026-09-06 17:00:00', 'Right knee swelling and pain', NULL, 'Discharged', NULL, NULL),
(405, 105, 206, NULL, 'Appointment', '2026-09-08 09:30:00', 'High grade fever with chills', NULL, 'Discharged', NULL, NULL),
(406, 106, 202, 301, 'Appointment', '2026-09-10 10:30:00', 'Severe abdominal pain', NULL, 'Discharged', '2026-09-10 12:00:00', '2026-09-13 10:00:00'),
(407, 107, 203, 305, 'Emergency', '2026-09-12 23:45:00', 'Acute appendicitis symptoms', 2, 'Admitted', '2026-09-13 01:00:00', NULL),
(408, 108, 201, 308, 'Appointment', '2026-09-14 09:00:00', 'Shortness of breath, fatigue', NULL, 'Admitted', '2026-09-14 11:00:00', NULL),
(409, 109, 208, NULL, 'Appointment', '2026-09-15 16:30:00', 'Routine antenatal checkup', NULL, 'Discharged', NULL, NULL),
(410, 110, 210, NULL, 'Appointment', '2026-09-16 11:00:00', 'Skin rash and itching', NULL, 'Discharged', NULL, NULL),
(411, 101, 201, NULL, 'Appointment', '2026-09-18 10:00:00', 'Post-discharge follow up', NULL, 'Discharged', NULL, NULL),
(412, 102, 209, NULL, 'Appointment', '2026-09-19 12:00:00', 'Follow up chest clear', NULL, 'Discharged', NULL, NULL),
(413, 111, 207, 309, 'Emergency', '2026-09-20 19:30:00', 'Road traffic accident, fracture', 2, 'Under Treatment', '2026-09-20 20:00:00', NULL),
(414, 112, 203, NULL, 'Emergency', '2026-09-21 21:00:00', 'Severe migraine, vomiting', 3, 'Discharged', NULL, NULL),
(415, 103, 205, NULL, 'Appointment', '2026-09-22 10:30:00', 'Neurology follow up', NULL, 'Scheduled', NULL, NULL),
(416, 104, 204, NULL, 'Emergency', '2026-09-22 14:00:00', 'Twisted ankle, unable to walk', 3, 'Waiting', NULL, NULL),
(417, 105, 206, NULL, 'Emergency', '2026-09-22 15:30:00', 'Mild asthma exacerbation', 4, 'Waiting', NULL, NULL),
(418, 106, 202, NULL, 'Emergency', '2026-09-22 16:00:00', 'Chest heaviness', 1, 'Waiting', NULL, NULL),
(419, 107, 209, NULL, 'Appointment', '2026-09-23 10:00:00', 'General health checkup', NULL, 'Scheduled', NULL, NULL),
(420, 108, 201, NULL, 'Appointment', '2026-09-23 11:00:00', 'Cardiology follow up', NULL, 'Scheduled', NULL, NULL);

-- Prescriptions (22 rows)
INSERT INTO prescription (prescription_id, visit_id, medicine_id, dosage, duration_days, quantity) VALUES
(601, 401, 503, '1 tab at night', 30, 30),
(602, 401, 509, '1 tab morning', 30, 30),
(603, 402, 502, '1 cap thrice daily', 5, 15),
(604, 402, 501, '1 tab as needed', 5, 10),
(605, 403, 506, '1g IV twice daily', 5, 10),
(606, 403, 505, '1 tab morning', 14, 14),
(607, 403, 507, '1 tab as needed', 3, 6),
(608, 404, 507, '1 tab twice daily', 5, 10),
(609, 404, 505, '1 tab morning', 7, 7),
(610, 405, 501, '1 tab as needed', 3, 6),
(611, 405, 508, '1 tab daily', 3, 3),
(612, 406, 505, '1 tab morning', 14, 14),
(613, 406, 506, '1g IV twice daily', 3, 6),
(614, 406, 507, '1 tab as needed', 5, 10),
(615, 407, 506, '1g IV stat then bd', 5, 10),
(616, 407, 507, '1 tab for pain', 5, 10),
(617, 407, 505, '1 tab morning', 10, 10),
(618, 408, 503, '1 tab night', 30, 30),
(619, 408, 509, '1 tab morning', 30, 30),
(620, 409, 501, '1 tab SOS', 5, 10),
(621, 410, 501, '1 tab SOS', 3, 6),
(622, 414, 510, '1 tab stat', 2, 4);

-- Bills (11 rows)
INSERT INTO bill (bill_id, visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_mode, payment_status, bill_date) VALUES
(701, 401, 800.00, 510.00, 7500.00, 8810.00, 'Card', 'Paid', '2026-09-04'),
(702, 402, 500.00, 145.00, 0.00, 645.00, 'UPI', 'Paid', '2026-09-03'),
(703, 403, 1000.00, 1073.00, 25000.00, 27073.00, 'Card', 'Paid', '2026-09-10'),
(704, 404, 700.00, 216.50, 0.00, 916.50, 'Cash', 'Paid', '2026-09-06'),
(705, 405, 600.00, 81.00, 0.00, 681.00, 'UPI', 'Paid', '2026-09-08'),
(706, 406, 500.00, 793.00, 1800.00, 3093.00, 'Card', 'Paid', '2026-09-13'),
(707, 407, 1000.00, 1095.00, 2500.00, 4595.00, NULL, 'Pending', '2026-09-14'),
(708, 408, 800.00, 510.00, 5000.00, 6310.00, NULL, 'Pending', '2026-09-15'),
(709, 409, 750.00, 25.00, 0.00, 775.00, 'UPI', 'Paid', '2026-09-15'),
(710, 410, 550.00, 15.00, 0.00, 565.00, 'Cash', 'Paid', '2026-09-16'),
(711, 414, 1000.00, 30.00, 0.00, 1030.00, 'Card', 'Paid', '2026-09-21');

-- Audit Log (12 rows)
INSERT INTO audit_log (log_id, table_name, action_type, record_id, changed_by, change_time, description) VALUES
(1, 'PATIENT', 'INSERT', 101, 'ADMIN', '2026-09-01 09:00:00', 'New patient registered: Arjun Reddy'),
(2, 'VISIT', 'INSERT', 401, 'RECEPTION1', '2026-09-01 10:00:00', 'Appointment booked with Dr. Rajesh Kumar'),
(3, 'VISIT', 'UPDATE', 401, 'DR_RKUMAR', '2026-09-01 11:00:00', 'Patient admitted to Private ward bed 305'),
(4, 'PRESCRIPTION', 'INSERT', 601, 'DR_RKUMAR', '2026-09-01 11:30:00', 'Prescribed Atorvastatin 10mg (qty 30)'),
(5, 'BILL', 'INSERT', 701, 'BILLING1', '2026-09-04 15:30:00', 'Bill generated for visit 401, total 8810'),
(6, 'BILL', 'UPDATE', 701, 'BILLING1', '2026-09-04 16:00:00', 'Bill 701 marked Paid via Card'),
(7, 'VISIT', 'UPDATE', 401, 'DR_RKUMAR', '2026-09-04 16:00:00', 'Patient discharged, bed 305 marked Cleaning'),
(8, 'PATIENT', 'INSERT', 107, 'ADMIN', '2026-09-12 23:30:00', 'New patient registered: Aakash Gupta'),
(9, 'VISIT', 'INSERT', 407, 'TRIAGE_NURSE', '2026-09-12 23:45:00', 'Emergency arrival, triage level 2 Urgent'),
(10, 'VISIT', 'UPDATE', 407, 'DR_AMENON', '2026-09-13 01:00:00', 'Emergency patient admitted to Private bed 305'),
(11, 'MEDICINE', 'UPDATE', 501, 'PHARMACIST', '2026-09-15 08:00:00', 'Stock updated for Paracetamol: +200'),
(12, 'BED', 'UPDATE', 304, 'ADMIN', '2026-09-15 09:00:00', 'Bed 304 status changed from Cleaning to Free');

-- Re-enable audit triggers
ALTER TABLE patient ENABLE TRIGGER trg_audit_patient;
ALTER TABLE visit ENABLE TRIGGER trg_audit_visit;
ALTER TABLE visit ENABLE TRIGGER trg_doctor_status;
ALTER TABLE bill ENABLE TRIGGER trg_audit_bill;

-- Reset sequence counters to match Review II golden sequence values
SELECT setval(pg_get_serial_sequence('patient', 'patient_id'), 112);
SELECT setval(pg_get_serial_sequence('doctor', 'doctor_id'), 210);
SELECT setval(pg_get_serial_sequence('bed', 'bed_id'), 312);
SELECT setval(pg_get_serial_sequence('medicine', 'medicine_id'), 512);
SELECT setval(pg_get_serial_sequence('visit', 'visit_id'), 420);
SELECT setval(pg_get_serial_sequence('prescription', 'prescription_id'), 622);
SELECT setval(pg_get_serial_sequence('bill', 'bill_id'), 711);
SELECT setval(pg_get_serial_sequence('audit_log', 'log_id'), 12);
