-- Smart Hospital Management System
-- Oracle SQL / SQL*Plus script generated from the supplied DBMS Review II document.
-- Run in a dedicated schema. DDL statements auto-commit in Oracle.
-- Core schema, sample data, report queries, functions, procedures, and triggers.
SET SERVEROUTPUT ON;
SET LINESIZE 200
SET PAGESIZE 100
CREATE TABLE patient (
patient_id         NUMBER        NOT NULL,
patient_name       VARCHAR2(50)  NOT NULL,
gender             VARCHAR2(10),
date_of_birth      DATE          NOT NULL,
phone              VARCHAR2(15)  NOT NULL,
address            VARCHAR2(100),
blood_group        VARCHAR2(5),
emergency_contact  VARCHAR2(15),
registration_date  DATE          DEFAULT SYSDATE,
CONSTRAINT pk_patient     PRIMARY KEY (patient_id),
CONSTRAINT uq_pat_phone   UNIQUE (phone),
CONSTRAINT chk_pat_gender CHECK (gender IN ('Male','Female','Other')),
CONSTRAINT chk_pat_phone  CHECK (REGEXP_LIKE(phone, '^[0-9]{10}$')),
CONSTRAINT chk_pat_blood  CHECK (blood_group IN
('A+','A-','B+','B-','AB+','AB-','O+','O-'))
);

CREATE TABLE doctor (
doctor_id            NUMBER        NOT NULL,
doctor_name          VARCHAR2(50)  NOT NULL,
department           VARCHAR2(30)  NOT NULL,
specialization       VARCHAR2(40),
phone                VARCHAR2(15),
consultation_fee     NUMBER(8,2)   NOT NULL,
shift                VARCHAR2(10),
availability_status  VARCHAR2(10)  DEFAULT 'Available' NOT NULL,
CONSTRAINT pk_doctor      PRIMARY KEY (doctor_id),
CONSTRAINT uq_doc_phone   UNIQUE (phone),
CONSTRAINT chk_doc_fee    CHECK (consultation_fee > 0),
CONSTRAINT chk_doc_shift  CHECK (shift IN ('Morning','Evening','Night')),
CONSTRAINT chk_doc_avail  CHECK (availability_status IN ('Available','Busy'))
);

CREATE TABLE bed (
bed_id        NUMBER       NOT NULL,
ward_type     VARCHAR2(15) NOT NULL,
bed_status    VARCHAR2(10) DEFAULT 'Free' NOT NULL,
daily_charge  NUMBER(8,2)  NOT NULL,
CONSTRAINT pk_bed        PRIMARY KEY (bed_id),
CONSTRAINT chk_bed_ward  CHECK (ward_type IN
('General','Private','ICU','Emergency')),
CONSTRAINT chk_bed_stat  CHECK (bed_status IN ('Free','Occupied','Cleaning')),
CONSTRAINT chk_bed_chg   CHECK (daily_charge > 0)
);

CREATE TABLE medicine (
medicine_id     NUMBER        NOT NULL,
medicine_name   VARCHAR2(50)  NOT NULL,
manufacturer    VARCHAR2(50),
price_per_unit  NUMBER(8,2)   NOT NULL,
stock_quantity  NUMBER        DEFAULT 0 NOT NULL,
CONSTRAINT pk_medicine    PRIMARY KEY (medicine_id),
CONSTRAINT chk_med_price  CHECK (price_per_unit > 0),
CONSTRAINT chk_med_stock  CHECK (stock_quantity >= 0)
);

CREATE TABLE visit (
visit_id        NUMBER        NOT NULL,
patient_id      NUMBER        NOT NULL,
doctor_id       NUMBER        NOT NULL,
bed_id          NUMBER,
visit_type      VARCHAR2(12)  NOT NULL,
visit_datetime  TIMESTAMP     NOT NULL,
complaint       VARCHAR2(100),
triage_level    NUMBER(1),
visit_status    VARCHAR2(15)  DEFAULT 'Scheduled' NOT NULL,
admit_time      TIMESTAMP,
discharge_time  TIMESTAMP,
CONSTRAINT pk_visit          PRIMARY KEY (visit_id),
CONSTRAINT fk_visit_patient  FOREIGN KEY (patient_id)
REFERENCES patient (patient_id),
CONSTRAINT fk_visit_doctor   FOREIGN KEY (doctor_id)
REFERENCES doctor (doctor_id),
CONSTRAINT fk_visit_bed      FOREIGN KEY (bed_id)
REFERENCES bed (bed_id),
CONSTRAINT chk_visit_type    CHECK (visit_type IN ('Appointment','Emergency')),
CONSTRAINT chk_visit_status  CHECK (visit_status IN ('Scheduled','Waiting',
'Under Treatment','Admitted','Discharged',
'Cancelled')),
CONSTRAINT chk_visit_range   CHECK (triage_level BETWEEN 1 AND 4),
CONSTRAINT chk_visit_triage  CHECK (
(visit_type = 'Emergency'   AND triage_level IS NOT NULL) OR
(visit_type = 'Appointment' AND triage_level IS NULL)),
CONSTRAINT chk_visit_bed     CHECK (visit_status <> 'Admitted'
OR bed_id IS NOT NULL),
CONSTRAINT chk_visit_disch   CHECK (discharge_time >= admit_time)
);

CREATE TABLE prescription (
prescription_id  NUMBER        NOT NULL,
visit_id         NUMBER        NOT NULL,
medicine_id      NUMBER        NOT NULL,
dosage           VARCHAR2(30),
duration_days    NUMBER,
quantity         NUMBER,
CONSTRAINT pk_prescription  PRIMARY KEY (prescription_id),
CONSTRAINT fk_presc_visit   FOREIGN KEY (visit_id)
REFERENCES visit (visit_id) ON DELETE CASCADE,
CONSTRAINT fk_presc_med     FOREIGN KEY (medicine_id)
REFERENCES medicine (medicine_id),
CONSTRAINT chk_presc_days   CHECK (duration_days > 0),
CONSTRAINT chk_presc_qty    CHECK (quantity > 0)
);

CREATE TABLE bill (
bill_id              NUMBER        NOT NULL,
visit_id             NUMBER        NOT NULL,
consultation_charge  NUMBER(8,2)   DEFAULT 0 NOT NULL,
medicine_charge      NUMBER(8,2)   DEFAULT 0 NOT NULL,
bed_charge           NUMBER(8,2)   DEFAULT 0 NOT NULL,
total_amount         NUMBER(10,2)  NOT NULL,
payment_mode         VARCHAR2(10),
payment_status       VARCHAR2(10)  DEFAULT 'Pending' NOT NULL,
bill_date            DATE          DEFAULT SYSDATE,
CONSTRAINT pk_bill         PRIMARY KEY (bill_id),
CONSTRAINT uq_bill_visit   UNIQUE (visit_id),
CONSTRAINT fk_bill_visit   FOREIGN KEY (visit_id)
REFERENCES visit (visit_id),
CONSTRAINT chk_bill_mode   CHECK (payment_mode IN ('Cash','Card','UPI')),
CONSTRAINT chk_bill_stat   CHECK (payment_status IN ('Paid','Pending')),
CONSTRAINT chk_bill_amt    CHECK (consultation_charge >= 0
AND medicine_charge >= 0 AND bed_charge >= 0),
CONSTRAINT chk_bill_total  CHECK (total_amount = consultation_charge
+ medicine_charge + bed_charge),
CONSTRAINT chk_bill_paid   CHECK (payment_status = 'Pending'
OR payment_mode IS NOT NULL)
);

CREATE TABLE audit_log (
log_id       NUMBER         NOT NULL,
table_name   VARCHAR2(30)   NOT NULL,
action_type  VARCHAR2(10)   NOT NULL,
record_id    NUMBER,
changed_by   VARCHAR2(30)   DEFAULT USER,
change_time  TIMESTAMP      DEFAULT SYSTIMESTAMP,
description  VARCHAR2(200),
CONSTRAINT pk_audit_log   PRIMARY KEY (log_id),
CONSTRAINT chk_audit_act  CHECK (action_type IN ('INSERT','UPDATE','DELETE'))
);

CREATE UNIQUE INDEX uq_doctor_slot ON visit (
CASE WHEN visit_status <> 'Cancelled' THEN doctor_id END,
CASE WHEN visit_status <> 'Cancelled' THEN visit_datetime END
);

CREATE UNIQUE INDEX uq_active_bed ON visit (
CASE WHEN visit_status = 'Admitted' THEN bed_id END
);

CREATE INDEX idx_visit_patient ON visit (patient_id);
CREATE INDEX idx_visit_doctor  ON visit (doctor_id);

CREATE INDEX idx_presc_visit   ON prescription (visit_id);

Sequences for the primary keys (start values continue after the sample data)
CREATE SEQUENCE seq_patient       START WITH 113 INCREMENT BY 1 NOCACHE;

CREATE SEQUENCE seq_visit         START WITH 421 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_prescription  START WITH 623 INCREMENT BY 1 NOCACHE;

CREATE SEQUENCE seq_bill          START WITH 712 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_audit         START WITH 13  INCREMENT BY 1 NOCACHE;

INSERT INTO patient VALUES (101, 'Arjun Reddy', 'Male', DATE '1985-03-14',
'9876500101', '12 Gandhi Road, Chennai', 'B+', '9876511101', DATE '2026-01-10');

INSERT INTO patient VALUES (102, 'Kavita Sharma', 'Female', DATE '1972-07-22',
'9876500102', '45 MG Road, Bengaluru', 'O+', '9876511102', DATE '2026-01-18');

INSERT INTO patient VALUES (103, 'Rahul Verma', 'Male', DATE '1990-11-05',
'9876500103', '7 Lake View, Hyderabad', 'A+', '9876511103', DATE '2026-02-02');

INSERT INTO patient VALUES (104, 'Divya Krishnan', 'Female', DATE '1998-01-30',
'9876500104', '23 Anna Nagar, Chennai', 'AB+', '9876511104', DATE '2026-02-14');

INSERT INTO patient VALUES (105, 'Mohammed Irfan', 'Male', DATE '2018-05-19',
'9876500105', '18 Park Street, Kolkata', 'O-', '9876511105', DATE '2026-03-05');

INSERT INTO patient VALUES (106, 'Sunita Patil', 'Female', DATE '1965-09-09',
'9876500106', '5 FC Road, Pune', 'B-', '9876511106', DATE '2026-03-21');

INSERT INTO patient VALUES (107, 'Aakash Gupta', 'Male', DATE '2001-12-12',
'9876500107', '88 Civil Lines, Delhi', 'A-', '9876511107', DATE '2026-04-11');

INSERT INTO patient VALUES (108, 'Lakshmi Narayanan', 'Female', DATE '1958-02-27',
'9876500108', '9 Temple Street, Madurai', 'O+', '9876511108', DATE '2026-05-02');

INSERT INTO patient VALUES (109, 'Vivek Joshi', 'Male', DATE '1979-06-18',
'9876500109', '31 Residency Road, Bengaluru', 'B+', '9876511109',
DATE '2026-06-15');

INSERT INTO patient VALUES (110, 'Neha Kapoor', 'Female', DATE '1988-04-03',
'9876500110', '14 Sector 21, Noida', 'A+', '9876511110', DATE '2026-07-08');

INSERT INTO patient VALUES (111, 'Imran Khan', 'Male', DATE '1995-08-25',
'9876500111', '2 Mount Road, Chennai', 'AB-', '9876511111', DATE '2026-09-14');

INSERT INTO patient VALUES (112, 'Pooja Menon', 'Female', DATE '1993-12-01',
'9876500112', '6 Marine Drive, Kochi', 'O+', '9876511112', DATE '2026-09-15');

INSERT INTO doctor VALUES (201, 'Dr. Rajesh Kumar', 'Cardiology', 'Cardiologist',
'9840011101', 800, 'Morning', 'Available');

INSERT INTO doctor VALUES (202, 'Dr. Priya Nair', 'General Medicine', 'Physician',
'9840011102', 500, 'Morning', 'Available');

INSERT INTO doctor VALUES (203, 'Dr. Arvind Menon', 'Emergency',
'Emergency Physician', '9840011103', 1000, 'Night', 'Available');

INSERT INTO doctor VALUES (204, 'Dr. Sneha Iyer', 'Orthopedics',
'Orthopedic Surgeon', '9840011104', 700, 'Evening', 'Available');

INSERT INTO doctor VALUES (205, 'Dr. Karthik Raman', 'Neurology', 'Neurologist',
'9840011105', 900, 'Morning', 'Available');

INSERT INTO doctor VALUES (206, 'Dr. Fatima Sheikh', 'Pediatrics', 'Pediatrician',
'9840011106', 600, 'Morning', 'Available');

INSERT INTO doctor VALUES (207, 'Dr. Vikram Singh', 'Emergency', 'Trauma Specialist',
'9840011107', 1000, 'Evening', 'Busy');

INSERT INTO doctor VALUES (208, 'Dr. Meena Pillai', 'Gynecology', 'Gynecologist',
'9840011108', 750, 'Evening', 'Available');

INSERT INTO doctor VALUES (209, 'Dr. Suresh Babu', 'General Medicine', 'Physician',
'9840011109', 500, 'Evening', 'Available');

INSERT INTO doctor VALUES (210, 'Dr. Anita Desai', 'Dermatology', 'Dermatologist',
'9840011110', 550, 'Morning', 'Available');

INSERT INTO bed VALUES (301, 'General', 'Free', 600);
INSERT INTO bed VALUES (302, 'General', 'Free', 600);

INSERT INTO bed VALUES (303, 'General', 'Free', 600);
INSERT INTO bed VALUES (304, 'General', 'Cleaning', 600);

INSERT INTO bed VALUES (305, 'Private', 'Occupied', 2500);
INSERT INTO bed VALUES (306, 'Private', 'Free', 2500);

INSERT INTO bed VALUES (307, 'ICU', 'Free', 5000);
INSERT INTO bed VALUES (308, 'ICU', 'Occupied', 5000);

INSERT INTO bed VALUES (309, 'Emergency', 'Free', 1500);
INSERT INTO bed VALUES (310, 'Emergency', 'Free', 1500);

INSERT INTO bed VALUES (311, 'Emergency', 'Free', 1500);
INSERT INTO bed VALUES (312, 'Emergency', 'Cleaning', 1500);

INSERT INTO medicine VALUES (501, 'Paracetamol 500mg', 'Cipla', 2.00, 480);
INSERT INTO medicine VALUES (502, 'Amoxicillin 500mg', 'Sun Pharma', 8.50, 276);

INSERT INTO medicine VALUES (503, 'Cetirizine 10mg', 'Dr. Reddys', 3.00, 388);
INSERT INTO medicine VALUES (504, 'Ibuprofen 400mg', 'Abbott', 4.50, 311);

INSERT INTO medicine VALUES (505, 'Pantoprazole 40mg', 'Cipla', 6.00, 238);
INSERT INTO medicine VALUES (506, 'Aspirin 75mg', 'Bayer', 1.50, 550);

INSERT INTO medicine VALUES (507, 'Atorvastatin 10mg', 'Lupin', 9.00, 160);
INSERT INTO medicine VALUES (508, 'Metformin 500mg', 'USV', 2.50, 270);

INSERT INTO medicine VALUES (509, 'Azithromycin 500mg', 'Alkem', 22.00, 8);
INSERT INTO medicine VALUES (510, 'Sumatriptan 50mg', 'Sun Pharma', 35.00, 5);

INSERT INTO medicine VALUES (511, 'Calcium + Vitamin D3', 'Torrent', 7.00, 120);
INSERT INTO medicine VALUES (512, 'ORS Sachet', 'FDC', 12.00, 0);

INSERT INTO visit VALUES (401, 107, 210, NULL, 'Appointment',
TIMESTAMP '2026-09-20 10:30:00', 'Skin rash', NULL, 'Discharged', NULL, NULL);

INSERT INTO visit VALUES (402, 108, 209, NULL, 'Appointment',
TIMESTAMP '2026-09-22 17:00:00', 'Diabetes review', NULL, 'Discharged', NULL,
NULL);

INSERT INTO visit VALUES (403, 110, 202, NULL, 'Appointment',
TIMESTAMP '2026-09-25 09:45:00', 'Persistent cough', NULL, 'Discharged', NULL,
NULL);

INSERT INTO visit VALUES (404, 109, 204, NULL, 'Appointment',
TIMESTAMP '2026-09-28 18:00:00', 'Lower back pain', NULL, 'Discharged', NULL,
NULL);

INSERT INTO visit VALUES (405, 101, 202, NULL, 'Appointment',
TIMESTAMP '2026-10-01 10:00:00', 'Fever and cold', NULL, 'Discharged', NULL, NULL);

INSERT INTO visit VALUES (406, 102, 201, NULL, 'Appointment',
TIMESTAMP '2026-10-01 11:30:00', 'Chest discomfort', NULL, 'Discharged', NULL,
NULL);

INSERT INTO visit VALUES (407, 103, 203, 307, 'Emergency',
TIMESTAMP '2026-10-02 22:15:00', 'Road accident - head injury', 1, 'Discharged',
TIMESTAMP '2026-10-02 22:40:00', TIMESTAMP '2026-10-05 11:00:00');

INSERT INTO visit VALUES (408, 104, 204, NULL, 'Appointment',
TIMESTAMP '2026-10-03 16:00:00', 'Knee pain', NULL, 'Discharged', NULL, NULL);

INSERT INTO visit VALUES (409, 105, 206, NULL, 'Appointment',
TIMESTAMP '2026-10-04 09:30:00', 'Child fever', NULL, 'Discharged', NULL, NULL);

INSERT INTO visit VALUES (410, 106, 207, 310, 'Emergency',
TIMESTAMP '2026-10-06 18:20:00', 'Fracture after fall from stairs', 2,
'Discharged', TIMESTAMP '2026-10-06 19:00:00', TIMESTAMP '2026-10-08 12:00:00');

INSERT INTO visit VALUES (411, 107, 205, NULL, 'Appointment',
TIMESTAMP '2026-10-07 11:00:00', 'Recurring migraine', NULL, 'Discharged', NULL,
NULL);

INSERT INTO visit VALUES (412, 108, 208, NULL, 'Appointment',
TIMESTAMP '2026-10-08 15:30:00', 'Routine check-up', NULL, 'Cancelled', NULL,
NULL);

INSERT INTO visit VALUES (413, 109, 201, 305, 'Appointment',
TIMESTAMP '2026-10-09 10:00:00', 'Chest pain - observation', NULL, 'Admitted',
TIMESTAMP '2026-10-09 12:00:00', NULL);

INSERT INTO visit VALUES (414, 110, 203, 308, 'Emergency',
TIMESTAMP '2026-10-10 02:30:00', 'Severe breathlessness', 1, 'Admitted',
TIMESTAMP '2026-10-10 03:00:00', NULL);

INSERT INTO visit VALUES (415, 111, 207, NULL, 'Emergency',
TIMESTAMP '2026-10-12 20:10:00', 'Deep cut on hand', 3, 'Under Treatment', NULL,
NULL);

INSERT INTO visit VALUES (416, 112, 203, NULL, 'Emergency',
TIMESTAMP '2026-10-12 20:25:00', 'High fever and vomiting', 2, 'Waiting', NULL,
NULL);

INSERT INTO visit VALUES (417, 103, 207, NULL, 'Emergency',
TIMESTAMP '2026-10-12 20:40:00', 'Minor ankle sprain', 4, 'Waiting', NULL, NULL);

INSERT INTO visit VALUES (418, 104, 203, NULL, 'Emergency',
TIMESTAMP '2026-10-12 20:50:00', 'Severe allergic reaction', 1, 'Waiting', NULL,
NULL);

INSERT INTO visit VALUES (419, 105, 202, NULL, 'Appointment',
TIMESTAMP '2026-10-14 10:00:00', 'Follow-up visit', NULL, 'Scheduled', NULL, NULL);

INSERT INTO visit VALUES (420, 102, 201, NULL, 'Appointment',
TIMESTAMP '2026-10-15 11:00:00', 'ECG follow-up', NULL, 'Scheduled', NULL, NULL);

INSERT INTO prescription VALUES (601, 401, 503, '0-0-1', 7, 7);
INSERT INTO prescription VALUES (602, 402, 508, '1-0-1', 30, 30);

INSERT INTO prescription VALUES (603, 403, 509, '1-0-0', 3, 3);
INSERT INTO prescription VALUES (604, 403, 501, '1-0-1', 3, 6);

INSERT INTO prescription VALUES (605, 404, 504, '1-0-1', 5, 10);
INSERT INTO prescription VALUES (606, 405, 501, '1-1-1', 3, 10);

INSERT INTO prescription VALUES (607, 405, 503, '0-0-1', 5, 5);
INSERT INTO prescription VALUES (608, 406, 506, '1-0-0', 30, 30);

INSERT INTO prescription VALUES (609, 406, 507, '0-0-1', 30, 30);
INSERT INTO prescription VALUES (610, 407, 502, '1-0-1', 7, 14);

INSERT INTO prescription VALUES (611, 407, 505, '1-0-0', 7, 7);
INSERT INTO prescription VALUES (612, 408, 504, '1-1-1', 5, 15);

INSERT INTO prescription VALUES (613, 408, 505, '1-0-0', 5, 5);
INSERT INTO prescription VALUES (614, 409, 501, '1-1-1', 3, 9);

INSERT INTO prescription VALUES (615, 410, 504, '1-0-1', 7, 14);
INSERT INTO prescription VALUES (616, 410, 511, '0-1-0', 30, 30);

INSERT INTO prescription VALUES (617, 411, 510, '1-0-0', 5, 5);
INSERT INTO prescription VALUES (618, 413, 506, '1-0-0', 10, 10);

INSERT INTO prescription VALUES (619, 413, 507, '0-0-1', 10, 10);
INSERT INTO prescription VALUES (620, 414, 506, '1-0-0', 10, 10);

INSERT INTO prescription VALUES (621, 414, 505, '1-0-0', 10, 10);
INSERT INTO prescription VALUES (622, 415, 502, '1-0-1', 5, 10);

INSERT INTO bill VALUES (701, 401, 550, 21, 0, 571, 'Cash', 'Paid',
DATE '2026-09-20');

INSERT INTO bill VALUES (702, 402, 500, 75, 0, 575, 'UPI', 'Paid',
DATE '2026-09-22');

INSERT INTO bill VALUES (703, 403, 500, 78, 0, 578, 'Card', 'Paid',
DATE '2026-09-25');

INSERT INTO bill VALUES (704, 404, 700, 45, 0, 745, 'UPI', 'Paid',
DATE '2026-09-28');

INSERT INTO bill VALUES (705, 405, 500, 35, 0, 535, 'Cash', 'Paid',
DATE '2026-10-01');

INSERT INTO bill VALUES (706, 406, 800, 315, 0, 1115, NULL, 'Pending',
DATE '2026-10-01');

INSERT INTO bill VALUES (707, 407, 1000, 161, 15000, 16161, 'Card', 'Paid',
DATE '2026-10-05');

INSERT INTO bill VALUES (708, 408, 700, 97.5, 0, 797.5, NULL, 'Pending',
DATE '2026-10-03');

INSERT INTO bill VALUES (709, 409, 600, 18, 0, 618, 'Cash', 'Paid',
DATE '2026-10-04');

INSERT INTO bill VALUES (710, 410, 1000, 273, 3000, 4273, NULL, 'Pending',
DATE '2026-10-08');

INSERT INTO bill VALUES (711, 411, 900, 175, 0, 1075, NULL, 'Pending',
DATE '2026-10-07');

INSERT INTO audit_log VALUES (1, 'PATIENT', 'INSERT', 111, 'RECEPTION1',
TIMESTAMP '2026-09-14 09:12:05', 'New patient registered');

INSERT INTO audit_log VALUES (2, 'PATIENT', 'INSERT', 112, 'RECEPTION1',
TIMESTAMP '2026-09-15 10:03:41', 'New patient registered');

INSERT INTO audit_log VALUES (3, 'VISIT', 'INSERT', 412, 'RECEPTION1',
TIMESTAMP '2026-10-05 12:20:10', 'New Appointment visit for patient 108');

INSERT INTO audit_log VALUES (4, 'VISIT', 'UPDATE', 412, 'RECEPTION1',
TIMESTAMP '2026-10-07 16:45:02', 'Status Scheduled -> Cancelled');

INSERT INTO audit_log VALUES (5, 'VISIT', 'INSERT', 413, 'RECEPTION1',
TIMESTAMP '2026-10-08 09:55:33', 'New Appointment visit for patient 109');

INSERT INTO audit_log VALUES (6, 'VISIT', 'UPDATE', 413, 'DR_RKUMAR',
TIMESTAMP '2026-10-09 12:00:17', 'Status Scheduled -> Admitted');

INSERT INTO audit_log VALUES (7, 'VISIT', 'INSERT', 414, 'TRIAGE_NURSE',
TIMESTAMP '2026-10-10 02:30:09', 'New Emergency visit for patient 110');

INSERT INTO audit_log VALUES (8, 'VISIT', 'UPDATE', 414, 'DR_AMENON',
TIMESTAMP '2026-10-10 03:00:48', 'Status Waiting -> Admitted');

INSERT INTO audit_log VALUES (9, 'VISIT', 'INSERT', 415, 'TRIAGE_NURSE',
TIMESTAMP '2026-10-12 20:10:21', 'New Emergency visit for patient 111');

INSERT INTO audit_log VALUES (10, 'VISIT', 'UPDATE', 415, 'DR_VSINGH',
TIMESTAMP '2026-10-12 20:18:50', 'Status Waiting -> Under Treatment');

INSERT INTO audit_log VALUES (11, 'BILL', 'INSERT', 710, 'BILLING1',
TIMESTAMP '2026-10-08 12:30:12', 'Bill generated: total 4273 (Pending)');

INSERT INTO audit_log VALUES (12, 'BILL', 'INSERT', 711, 'BILLING1',
TIMESTAMP '2026-10-07 11:40:55', 'Bill generated: total 1075 (Pending)');

COMMIT;

Row-count check
SELECT 'PATIENT' AS table_name, COUNT(*) AS row_count FROM patient
UNION ALL
SELECT 'DOCTOR' AS table_name, COUNT(*) AS row_count FROM doctor
UNION ALL
SELECT 'BED' AS table_name, COUNT(*) AS row_count FROM bed
UNION ALL
SELECT 'MEDICINE' AS table_name, COUNT(*) AS row_count FROM medicine
UNION ALL
SELECT 'VISIT' AS table_name, COUNT(*) AS row_count FROM visit
UNION ALL
SELECT 'PRESCRIPTION' AS table_name, COUNT(*) AS row_count FROM prescription
UNION ALL
SELECT 'BILL' AS table_name, COUNT(*) AS row_count FROM bill
UNION ALL
SELECT 'AUDIT_LOG' AS table_name, COUNT(*) AS row_count FROM audit_log;

SELECT v.visit_id,
TO_CHAR(v.visit_datetime, 'YYYY-MM-DD HH24:MI') AS visit_time,
v.visit_type, d.doctor_name, v.complaint, v.visit_status
FROM patient p
JOIN visit  v ON v.patient_id = p.patient_id
JOIN doctor d ON d.doctor_id  = v.doctor_id
WHERE p.patient_name = 'Aakash Gupta'
ORDER BY v.visit_datetime;

SELECT d.doctor_name, d.department, COUNT(v.visit_id) AS total_visits
FROM doctor d
LEFT JOIN visit v ON v.doctor_id = d.doctor_id
GROUP BY d.doctor_name, d.department
ORDER BY total_visits DESC, d.doctor_name;

SELECT triage_level,
CASE triage_level WHEN 1 THEN 'Critical' WHEN 2 THEN 'Very urgent'
WHEN 3 THEN 'Urgent'   ELSE 'Minor' END AS category,
COUNT(*) AS cases
FROM visit
WHERE visit_type = 'Emergency'
GROUP BY triage_level
ORDER BY triage_level;

SELECT d.department, COUNT(*) AS total_visits
FROM doctor d
JOIN visit v ON v.doctor_id = d.doctor_id
WHERE v.visit_status <> 'Cancelled'
GROUP BY d.department
HAVING COUNT(*) >= 3
ORDER BY total_visits DESC, d.department;

SELECT medicine_id, medicine_name, stock_quantity
FROM medicine
WHERE stock_quantity < 20
ORDER BY stock_quantity;

SELECT ward_type, COUNT(*) AS free_beds, MIN(daily_charge) AS daily_charge
FROM bed
WHERE bed_status = 'Free'
GROUP BY ward_type
ORDER BY ward_type;

SELECT ward_type,
COUNT(*) AS total_beds,
SUM(CASE WHEN bed_status = 'Occupied' THEN 1 ELSE 0 END) AS occupied,
ROUND(100.0 * SUM(CASE WHEN bed_status = 'Occupied' THEN 1 ELSE 0 END)
/ COUNT(*), 1) AS occupancy_pct
FROM bed
GROUP BY ward_type
ORDER BY ward_type;

SELECT payment_status, COUNT(*) AS bills, SUM(total_amount) AS amount
FROM bill
GROUP BY payment_status
ORDER BY payment_status;

SELECT TO_CHAR(bill_date, 'YYYY-MM') AS bill_month,
COUNT(*) AS bills,
SUM(consultation_charge) AS consultation,
SUM(medicine_charge)     AS medicine,
SUM(bed_charge)          AS beds,
SUM(total_amount)        AS total
FROM bill
GROUP BY TO_CHAR(bill_date, 'YYYY-MM')
ORDER BY bill_month;

SELECT b.bill_id, p.patient_name, d.doctor_name, b.total_amount
FROM bill b
JOIN visit   v ON v.visit_id   = b.visit_id
JOIN patient p ON p.patient_id = v.patient_id
JOIN doctor  d ON d.doctor_id  = v.doctor_id
WHERE b.payment_status = 'Pending'
ORDER BY b.total_amount DESC;

SELECT p.patient_id, p.patient_name, p.blood_group
FROM patient p
WHERE NOT EXISTS (SELECT 1
FROM visit v
WHERE v.patient_id = p.patient_id
AND v.visit_type = 'Emergency')
ORDER BY p.patient_id;

SELECT doctor_name, department, consultation_fee
FROM doctor
WHERE consultation_fee > (SELECT AVG(consultation_fee) FROM doctor)
ORDER BY consultation_fee DESC, doctor_name;

SELECT patient_name, total_billed, rnk
FROM (SELECT p.patient_name,
SUM(b.total_amount) AS total_billed,
RANK() OVER (ORDER BY SUM(b.total_amount) DESC) AS rnk
FROM bill b
JOIN visit   v ON v.visit_id   = b.visit_id
JOIN patient p ON p.patient_id = v.patient_id
GROUP BY p.patient_id, p.patient_name) t
WHERE rnk <= 3
ORDER BY rnk, patient_name;

SELECT m.medicine_name,
COUNT(*)                       AS times_prescribed,
SUM(pr.quantity)               AS units,
SUM(pr.quantity * m.price_per_unit) AS total_value
FROM prescription pr
JOIN medicine m ON m.medicine_id = pr.medicine_id
GROUP BY m.medicine_name
HAVING COUNT(*) > 1
ORDER BY units DESC, m.medicine_name;

SELECT v.visit_id, p.patient_name, v.visit_type, b.bed_id, b.ward_type,
b.daily_charge, d.doctor_name
FROM visit v
JOIN patient p ON p.patient_id = v.patient_id
JOIN bed     b ON b.bed_id     = v.bed_id
JOIN doctor  d ON d.doctor_id  = v.doctor_id
WHERE v.visit_status = 'Admitted'
ORDER BY b.ward_type, v.visit_id;

SELECT v.visit_id, p.patient_name, v.triage_level,
TO_CHAR(v.visit_datetime, 'HH24:MI') AS arrived, v.complaint
FROM visit v
JOIN patient p ON p.patient_id = v.patient_id
WHERE v.visit_type = 'Emergency' AND v.visit_status = 'Waiting'
ORDER BY v.triage_level, v.visit_datetime;

SELECT v.visit_type, COUNT(*) AS bills,
ROUND(AVG(b.total_amount), 2) AS avg_bill,
MAX(b.total_amount)           AS highest_bill
FROM bill b
JOIN visit v ON v.visit_id = b.visit_id
GROUP BY v.visit_type
ORDER BY v.visit_type;

SELECT doctor_id, doctor_name, department
FROM doctor
WHERE doctor_id IN (SELECT v.doctor_id
FROM visit v
JOIN prescription pr ON pr.visit_id = v.visit_id
JOIN medicine m ON m.medicine_id = pr.medicine_id
WHERE m.medicine_name LIKE 'Aspirin%')
ORDER BY doctor_id;

SELECT p.patient_name,
COUNT(*) AS visits,
TO_CHAR(MIN(v.visit_datetime), 'YYYY-MM-DD') AS first_visit,
TO_CHAR(MAX(v.visit_datetime), 'YYYY-MM-DD') AS last_visit
FROM patient p
JOIN visit v ON v.patient_id = p.patient_id
GROUP BY p.patient_id, p.patient_name
HAVING COUNT(*) > 1
ORDER BY visits DESC, p.patient_name;

CREATE OR REPLACE FUNCTION fn_days_stayed (p_visit_id IN NUMBER)
RETURN NUMBER
IS
v_admit  visit.admit_time%TYPE;
v_disch  visit.discharge_time%TYPE;
v_days   NUMBER;
BEGIN
SELECT admit_time, discharge_time
INTO v_admit, v_disch
FROM visit
WHERE visit_id = p_visit_id;

IF v_admit IS NULL THEN
RETURN 0;                                  -- never admitted: no bed days
END IF;

v_days := TRUNC(CAST(NVL(v_disch, LOCALTIMESTAMP) AS DATE))
- TRUNC(CAST(v_admit AS DATE));
RETURN GREATEST(v_days, 1);                  -- at least one day is charged
EXCEPTION
WHEN NO_DATA_FOUND THEN
RAISE_APPLICATION_ERROR(-20001, 'Visit ' || p_visit_id || ' does not exist');
END fn_days_stayed;
/

CREATE OR REPLACE FUNCTION fn_medicine_cost (p_visit_id IN NUMBER)
RETURN NUMBER
IS
v_total  NUMBER;
BEGIN
SELECT NVL(SUM(pr.quantity * m.price_per_unit), 0)
INTO v_total
FROM prescription pr
JOIN medicine m ON m.medicine_id = pr.medicine_id
WHERE pr.visit_id = p_visit_id;

RETURN v_total;
END fn_medicine_cost;
/

CREATE OR REPLACE FUNCTION fn_triage_label (p_level IN NUMBER)
RETURN VARCHAR2
DETERMINISTIC
IS
BEGIN
RETURN CASE p_level
WHEN 1 THEN 'Critical'
WHEN 2 THEN 'Very urgent'
WHEN 3 THEN 'Urgent'
WHEN 4 THEN 'Minor'
ELSE 'Not triaged'
END;
END fn_triage_label;
/

SELECT visit_id,
fn_days_stayed(visit_id)   AS days_stayed,
fn_medicine_cost(visit_id) AS medicine_cost,
fn_triage_label(triage_level) AS triage
FROM visit
WHERE visit_id IN (405, 407, 410)
ORDER BY visit_id;

CREATE OR REPLACE PROCEDURE sp_book_appointment (
p_patient_id  IN  NUMBER,
p_doctor_id   IN  NUMBER,
p_slot        IN  TIMESTAMP,
p_complaint   IN  VARCHAR2,
p_visit_id    OUT NUMBER
)
IS
v_count  NUMBER;
BEGIN
SELECT COUNT(*) INTO v_count FROM patient WHERE patient_id = p_patient_id;
IF v_count = 0 THEN
RAISE_APPLICATION_ERROR(-20002, 'Patient ' || p_patient_id || ' is not registered');
END IF;

SELECT COUNT(*) INTO v_count FROM doctor WHERE doctor_id = p_doctor_id;
IF v_count = 0 THEN
RAISE_APPLICATION_ERROR(-20003, 'Doctor ' || p_doctor_id || ' does not exist');
END IF;

IF p_slot <= LOCALTIMESTAMP THEN
RAISE_APPLICATION_ERROR(-20004, 'Appointment time must be in the future');
END IF;

SELECT COUNT(*) INTO v_count
FROM visit
WHERE doctor_id = p_doctor_id
AND visit_datetime = p_slot
AND visit_status <> 'Cancelled';
IF v_count > 0 THEN
RAISE_APPLICATION_ERROR(-20005,
'Doctor ' || p_doctor_id || ' already has an appointment at that time');
END IF;

INSERT INTO visit (visit_id, patient_id, doctor_id, visit_type,
visit_datetime, complaint, visit_status)
VALUES (seq_visit.NEXTVAL, p_patient_id, p_doctor_id, 'Appointment',
p_slot, p_complaint, 'Scheduled')
RETURNING visit_id INTO p_visit_id;

COMMIT;
EXCEPTION
WHEN DUP_VAL_ON_INDEX THEN                   -- two users booking at once
ROLLBACK;
RAISE_APPLICATION_ERROR(-20005,
'Doctor ' || p_doctor_id || ' already has an appointment at that time');
END sp_book_appointment;
/

CREATE OR REPLACE PROCEDURE sp_register_emergency (
p_patient_id  IN  NUMBER,
p_complaint   IN  VARCHAR2,
p_triage      IN  NUMBER,
p_visit_id    OUT NUMBER,
p_arrival     IN  TIMESTAMP DEFAULT LOCALTIMESTAMP
)
IS
v_count   NUMBER;
v_doctor  doctor.doctor_id%TYPE;
BEGIN
IF p_triage NOT BETWEEN 1 AND 4 THEN
RAISE_APPLICATION_ERROR(-20010, 'Triage level must be between 1 and 4');
END IF;

SELECT COUNT(*) INTO v_count FROM patient WHERE patient_id = p_patient_id;
IF v_count = 0 THEN
RAISE_APPLICATION_ERROR(-20002, 'Patient ' || p_patient_id || ' is not registered');
END IF;

-- emergency doctor with the smallest number of active cases (ties: lowest id)
BEGIN
SELECT doctor_id
INTO v_doctor
FROM (SELECT d.doctor_id
FROM doctor d
WHERE d.department = 'Emergency'
ORDER BY (SELECT COUNT(*)
FROM visit v
WHERE v.doctor_id = d.doctor_id
AND v.visit_status IN ('Waiting', 'Under Treatment')),
d.doctor_id)
WHERE ROWNUM = 1;
EXCEPTION
WHEN NO_DATA_FOUND THEN
RAISE_APPLICATION_ERROR(-20011, 'No emergency doctor is available');
END;

INSERT INTO visit (visit_id, patient_id, doctor_id, visit_type, visit_datetime,
complaint, triage_level, visit_status)
VALUES (seq_visit.NEXTVAL, p_patient_id, v_doctor, 'Emergency', p_arrival,
p_complaint, p_triage, 'Waiting')
RETURNING visit_id INTO p_visit_id;

COMMIT;
END sp_register_emergency;
/

CREATE OR REPLACE PROCEDURE sp_allot_bed (
p_visit_id   IN  NUMBER,
p_ward_type  IN  VARCHAR2,
p_bed_id     OUT NUMBER
)
IS
v_status  visit.visit_status%TYPE;
v_bed     visit.bed_id%TYPE;
BEGIN
BEGIN
SELECT visit_status, bed_id
INTO v_status, v_bed
FROM visit
WHERE visit_id = p_visit_id
FOR UPDATE;
EXCEPTION
WHEN NO_DATA_FOUND THEN
RAISE_APPLICATION_ERROR(-20020, 'Visit ' || p_visit_id || ' does not exist');
END;

IF v_status IN ('Cancelled', 'Discharged') THEN
RAISE_APPLICATION_ERROR(-20021, 'Visit ' || p_visit_id || ' is already ' || v_status);
END IF;
IF v_bed IS NOT NULL THEN
RAISE_APPLICATION_ERROR(-20022, 'Visit ' || p_visit_id || ' already has a bed');
END IF;

BEGIN
SELECT bed_id
INTO p_bed_id
FROM bed
WHERE bed_id = (SELECT MIN(bed_id)
FROM bed
WHERE ward_type = p_ward_type
AND bed_status = 'Free')
FOR UPDATE;
EXCEPTION
WHEN NO_DATA_FOUND THEN
RAISE_APPLICATION_ERROR(-20023, 'No free bed in the ' || p_ward_type || ' ward');
END;

UPDATE bed
SET bed_status = 'Occupied'
WHERE bed_id = p_bed_id AND bed_status = 'Free';
IF SQL%ROWCOUNT = 0 THEN
RAISE_APPLICATION_ERROR(-20024, 'Bed ' || p_bed_id || ' was taken, try again');
END IF;

UPDATE visit
SET bed_id = p_bed_id,
admit_time = LOCALTIMESTAMP,
visit_status = 'Admitted'
WHERE visit_id = p_visit_id;

COMMIT;
END sp_allot_bed;
/

CREATE OR REPLACE PROCEDURE sp_discharge_patient (p_visit_id IN NUMBER)
IS
v_status  visit.visit_status%TYPE;
v_bed     visit.bed_id%TYPE;
BEGIN
BEGIN
SELECT visit_status, bed_id
INTO v_status, v_bed
FROM visit
WHERE visit_id = p_visit_id
FOR UPDATE;
EXCEPTION
WHEN NO_DATA_FOUND THEN
RAISE_APPLICATION_ERROR(-20030, 'Visit ' || p_visit_id || ' does not exist');
END;

IF v_status NOT IN ('Waiting', 'Under Treatment', 'Admitted') THEN
RAISE_APPLICATION_ERROR(-20031,
'Visit ' || p_visit_id || ' cannot be discharged from status ' || v_status);
END IF;

UPDATE visit
SET visit_status   = 'Discharged',
discharge_time = CASE WHEN bed_id IS NOT NULL THEN LOCALTIMESTAMP END
WHERE visit_id = p_visit_id;

IF v_bed IS NOT NULL THEN
UPDATE bed SET bed_status = 'Cleaning' WHERE bed_id = v_bed;
END IF;

COMMIT;
END sp_discharge_patient;
/

CREATE OR REPLACE PROCEDURE sp_emergency_queue
IS
CURSOR c_queue IS
SELECT v.visit_id, p.patient_name, v.triage_level, v.complaint,
d.doctor_name, v.visit_datetime
FROM visit v
JOIN patient p ON p.patient_id = v.patient_id
JOIN doctor  d ON d.doctor_id  = v.doctor_id
WHERE v.visit_type   = 'Emergency'
AND v.visit_status = 'Waiting'
ORDER BY v.triage_level, v.visit_datetime;

r  c_queue%ROWTYPE;
BEGIN
DBMS_OUTPUT.PUT_LINE('EMERGENCY WAITING LIST (highest priority first)');
DBMS_OUTPUT.PUT_LINE(RPAD('-', 70, '-'));

OPEN c_queue;
LOOP
FETCH c_queue INTO r;
EXIT WHEN c_queue%NOTFOUND;
DBMS_OUTPUT.PUT_LINE(c_queue%ROWCOUNT || '. [T' || r.triage_level || '] '
|| RPAD(fn_triage_label(r.triage_level), 11)
|| '| Visit ' || r.visit_id || ' | ' || r.patient_name
|| ' | arrived ' || TO_CHAR(r.visit_datetime, 'HH24:MI'));
DBMS_OUTPUT.PUT_LINE('      Complaint: ' || r.complaint
|| ' | ' || r.doctor_name);
END LOOP;

IF c_queue%ROWCOUNT = 0 THEN
DBMS_OUTPUT.PUT_LINE('No emergency patient is waiting.');
END IF;
CLOSE c_queue;
END sp_emergency_queue;
/

CREATE OR REPLACE PROCEDURE sp_pending_bills (p_min_amount IN NUMBER DEFAULT 0)
IS
CURSOR c_pending (cp_min NUMBER) IS
SELECT b.bill_id, p.patient_name, b.bill_date, b.total_amount
FROM bill b
JOIN visit   v ON v.visit_id   = b.visit_id
JOIN patient p ON p.patient_id = v.patient_id
WHERE b.payment_status = 'Pending'
AND b.total_amount  >= cp_min
ORDER BY b.bill_date, b.bill_id;

v_count  NUMBER := 0;
v_sum    NUMBER := 0;
BEGIN
DBMS_OUTPUT.PUT_LINE('PENDING BILLS (amount >= ' || p_min_amount || ')');
DBMS_OUTPUT.PUT_LINE(RPAD('-', 62, '-'));

FOR r IN c_pending(p_min_amount) LOOP
DBMS_OUTPUT.PUT_LINE('Bill ' || r.bill_id || ' | ' || RPAD(r.patient_name, 18)
|| ' | ' || TO_CHAR(r.bill_date, 'DD-Mon-YYYY')
|| ' | Rs. ' || TO_CHAR(r.total_amount, 'FM99,99,990.00'));
v_count := v_count + 1;
v_sum   := v_sum + r.total_amount;
END LOOP;

DBMS_OUTPUT.PUT_LINE(RPAD('-', 62, '-'));
DBMS_OUTPUT.PUT_LINE(v_count || ' bill(s) pending, total Rs. '
|| TO_CHAR(v_sum, 'FM99,99,990.00'));
END sp_pending_bills;
/

SET SERVEROUTPUT ON
EXEC sp_emergency_queue;

CREATE OR REPLACE PROCEDURE sp_write_audit (
p_table   IN VARCHAR2,
p_action  IN VARCHAR2,
p_record  IN NUMBER,
p_desc    IN VARCHAR2
)
IS
BEGIN
INSERT INTO audit_log (log_id, table_name, action_type, record_id, description)
VALUES (seq_audit.NEXTVAL, p_table, p_action, p_record, SUBSTR(p_desc, 1, 200));
END sp_write_audit;
/

CREATE OR REPLACE TRIGGER trg_reduce_stock
BEFORE INSERT OR DELETE ON prescription
FOR EACH ROW
DECLARE
v_stock  medicine.stock_quantity%TYPE;
v_name   medicine.medicine_name%TYPE;
BEGIN
IF INSERTING THEN
SELECT stock_quantity, medicine_name
INTO v_stock, v_name
FROM medicine
WHERE medicine_id = :NEW.medicine_id
FOR UPDATE;

IF v_stock < :NEW.quantity THEN
RAISE_APPLICATION_ERROR(-20060, 'Insufficient stock for ' || v_name
|| ': available ' || v_stock || ', requested ' || :NEW.quantity);
END IF;

UPDATE medicine
SET stock_quantity = stock_quantity - :NEW.quantity
WHERE medicine_id = :NEW.medicine_id;
ELSE                                          -- DELETING
UPDATE medicine
SET stock_quantity = stock_quantity + :OLD.quantity
WHERE medicine_id = :OLD.medicine_id;
END IF;
END trg_reduce_stock;
/

CREATE OR REPLACE TRIGGER trg_audit_visit
AFTER INSERT OR UPDATE OR DELETE ON visit
FOR EACH ROW
BEGIN
IF INSERTING THEN
sp_write_audit('VISIT', 'INSERT', :NEW.visit_id,
'New ' || :NEW.visit_type || ' visit for patient ' || :NEW.patient_id);
ELSIF UPDATING THEN
sp_write_audit('VISIT', 'UPDATE', :NEW.visit_id,
'Status ' || :OLD.visit_status || ' -> ' || :NEW.visit_status);
ELSE
sp_write_audit('VISIT', 'DELETE', :OLD.visit_id,
'Visit deleted (patient ' || :OLD.patient_id || ')');
END IF;
END trg_audit_visit;
/

CREATE OR REPLACE TRIGGER trg_audit_bill
AFTER INSERT OR UPDATE OR DELETE ON bill
FOR EACH ROW
BEGIN
IF INSERTING THEN
sp_write_audit('BILL', 'INSERT', :NEW.bill_id,
'Bill generated: total ' || :NEW.total_amount
|| ' (' || :NEW.payment_status || ')');
ELSIF UPDATING THEN
sp_write_audit('BILL', 'UPDATE', :NEW.bill_id,
'Payment status ' || :OLD.payment_status || ' -> ' || :NEW.payment_status);
ELSE
sp_write_audit('BILL', 'DELETE', :OLD.bill_id, 'Bill deleted');
END IF;
END trg_audit_bill;
/

CREATE OR REPLACE TRIGGER trg_audit_patient
AFTER INSERT OR UPDATE OR DELETE ON patient
FOR EACH ROW
BEGIN
IF INSERTING THEN
sp_write_audit('PATIENT', 'INSERT', :NEW.patient_id, 'New patient registered');
ELSIF UPDATING THEN
sp_write_audit('PATIENT', 'UPDATE', :NEW.patient_id, 'Patient details updated');
ELSE
sp_write_audit('PATIENT', 'DELETE', :OLD.patient_id, 'Patient record deleted');
END IF;
END trg_audit_patient;
/

CREATE OR REPLACE TRIGGER trg_doctor_status
AFTER INSERT OR UPDATE OF visit_status ON visit
FOR EACH ROW
BEGIN
IF :NEW.visit_status = 'Under Treatment' THEN
UPDATE doctor SET availability_status = 'Busy'
WHERE doctor_id = :NEW.doctor_id;
ELSIF UPDATING AND :OLD.visit_status = 'Under Treatment' THEN
UPDATE doctor SET availability_status = 'Available'
WHERE doctor_id = :NEW.doctor_id;
END IF;
END trg_doctor_status;
/

CREATE OR REPLACE TRIGGER trg_protect_audit
BEFORE UPDATE OR DELETE ON audit_log
BEGIN
RAISE_APPLICATION_ERROR(-20050, 'AUDIT_LOG entries cannot be modified or deleted');
END trg_protect_audit;
/

SELECT log_id, table_name, action_type, record_id, description
FROM audit_log
WHERE log_id > 12
ORDER BY log_id;

