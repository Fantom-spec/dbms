-- Smart Hospital Management System - SQLite Seed Data
-- Converted from Oracle Review II script
-- Run AFTER schema.sql, BEFORE triggers.sql
-- Triggers are created after seed so seed doesn't generate extra audit rows or reduce stock

-- ===== Patient (12 rows) =====
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

-- ===== Doctor (10 rows) =====
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

-- ===== Bed (12 rows) =====
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

-- ===== Medicine (12 rows) =====
INSERT INTO medicine (medicine_id, medicine_name, manufacturer, price_per_unit, stock_quantity) VALUES
(501, 'Paracetamol 500mg', 'Cipla', 2.00, 480),
(502, 'Amoxicillin 500mg', 'Sun Pharma', 8.50, 276),
(503, 'Cetirizine 10mg', 'Dr. Reddys', 3.00, 388),
(504, 'Ibuprofen 400mg', 'Abbott', 4.50, 311),
(505, 'Pantoprazole 40mg', 'Cipla', 6.00, 238),
(506, 'Aspirin 75mg', 'Bayer', 1.50, 550),
(507, 'Atorvastatin 10mg', 'Lupin', 9.00, 160),
(508, 'Metformin 500mg', 'USV', 2.50, 270),
(509, 'Azithromycin 500mg', 'Alkem', 22.00, 8),
(510, 'Sumatriptan 50mg', 'Sun Pharma', 35.00, 5),
(511, 'Calcium + Vitamin D3', 'Torrent', 7.00, 120),
(512, 'ORS Sachet', 'FDC', 12.00, 0);

-- ===== Visit (20 rows) =====
INSERT INTO visit (visit_id, patient_id, doctor_id, bed_id, visit_type, visit_datetime, complaint, triage_level, visit_status, admit_time, discharge_time) VALUES
(401, 107, 210, NULL, 'Appointment', '2026-09-20 10:30:00', 'Skin rash', NULL, 'Discharged', NULL, NULL),
(402, 108, 209, NULL, 'Appointment', '2026-09-22 17:00:00', 'Diabetes review', NULL, 'Discharged', NULL, NULL),
(403, 110, 202, NULL, 'Appointment', '2026-09-25 09:45:00', 'Persistent cough', NULL, 'Discharged', NULL, NULL),
(404, 109, 204, NULL, 'Appointment', '2026-09-28 18:00:00', 'Lower back pain', NULL, 'Discharged', NULL, NULL),
(405, 101, 202, NULL, 'Appointment', '2026-10-01 10:00:00', 'Fever and cold', NULL, 'Discharged', NULL, NULL),
(406, 102, 201, NULL, 'Appointment', '2026-10-01 11:30:00', 'Chest discomfort', NULL, 'Discharged', NULL, NULL),
(407, 103, 203, 307, 'Emergency', '2026-10-02 22:15:00', 'Road accident - head injury', 1, 'Discharged', '2026-10-02 22:40:00', '2026-10-05 11:00:00'),
(408, 104, 204, NULL, 'Appointment', '2026-10-03 16:00:00', 'Knee pain', NULL, 'Discharged', NULL, NULL),
(409, 105, 206, NULL, 'Appointment', '2026-10-04 09:30:00', 'Child fever', NULL, 'Discharged', NULL, NULL),
(410, 106, 207, 310, 'Emergency', '2026-10-06 18:20:00', 'Fracture after fall from stairs', 2, 'Discharged', '2026-10-06 19:00:00', '2026-10-08 12:00:00'),
(411, 107, 205, NULL, 'Appointment', '2026-10-07 11:00:00', 'Recurring migraine', NULL, 'Discharged', NULL, NULL),
(412, 108, 208, NULL, 'Appointment', '2026-10-08 15:30:00', 'Routine check-up', NULL, 'Cancelled', NULL, NULL),
(413, 109, 201, 305, 'Appointment', '2026-10-09 10:00:00', 'Chest pain - observation', NULL, 'Admitted', '2026-10-09 12:00:00', NULL),
(414, 110, 203, 308, 'Emergency', '2026-10-10 02:30:00', 'Severe breathlessness', 1, 'Admitted', '2026-10-10 03:00:00', NULL),
(415, 111, 207, NULL, 'Emergency', '2026-10-12 20:10:00', 'Deep cut on hand', 3, 'Under Treatment', NULL, NULL),
(416, 112, 203, NULL, 'Emergency', '2026-10-12 20:25:00', 'High fever and vomiting', 2, 'Waiting', NULL, NULL),
(417, 103, 207, NULL, 'Emergency', '2026-10-12 20:40:00', 'Minor ankle sprain', 4, 'Waiting', NULL, NULL),
(418, 104, 203, NULL, 'Emergency', '2026-10-12 20:50:00', 'Severe allergic reaction', 1, 'Waiting', NULL, NULL),
(419, 105, 202, NULL, 'Appointment', '2026-10-14 10:00:00', 'Follow-up visit', NULL, 'Scheduled', NULL, NULL),
(420, 102, 201, NULL, 'Appointment', '2026-10-15 11:00:00', 'ECG follow-up', NULL, 'Scheduled', NULL, NULL);

-- ===== Prescription (22 rows) =====
INSERT INTO prescription (prescription_id, visit_id, medicine_id, dosage, duration_days, quantity) VALUES
(601, 401, 503, '0-0-1', 7, 7),
(602, 402, 508, '1-0-1', 30, 30),
(603, 403, 509, '1-0-0', 3, 3),
(604, 403, 501, '1-0-1', 3, 6),
(605, 404, 504, '1-0-1', 5, 10),
(606, 405, 501, '1-1-1', 3, 10),
(607, 405, 503, '0-0-1', 5, 5),
(608, 406, 506, '1-0-0', 30, 30),
(609, 406, 507, '0-0-1', 30, 30),
(610, 407, 502, '1-0-1', 7, 14),
(611, 407, 505, '1-0-0', 7, 7),
(612, 408, 504, '1-1-1', 5, 15),
(613, 408, 505, '1-0-0', 5, 5),
(614, 409, 501, '1-1-1', 3, 9),
(615, 410, 504, '1-0-1', 7, 14),
(616, 410, 511, '0-1-0', 30, 30),
(617, 411, 510, '1-0-0', 5, 5),
(618, 413, 506, '1-0-0', 10, 10),
(619, 413, 507, '0-0-1', 10, 10),
(620, 414, 506, '1-0-0', 10, 10),
(621, 414, 505, '1-0-0', 10, 10),
(622, 415, 502, '1-0-1', 5, 10);

-- ===== Bill (11 rows) =====
INSERT INTO bill (bill_id, visit_id, consultation_charge, medicine_charge, bed_charge, total_amount, payment_mode, payment_status, bill_date) VALUES
(701, 401, 550, 21, 0, 571, 'Cash', 'Paid', '2026-09-20'),
(702, 402, 500, 75, 0, 575, 'UPI', 'Paid', '2026-09-22'),
(703, 403, 500, 78, 0, 578, 'Card', 'Paid', '2026-09-25'),
(704, 404, 700, 45, 0, 745, 'UPI', 'Paid', '2026-09-28'),
(705, 405, 500, 35, 0, 535, 'Cash', 'Paid', '2026-10-01'),
(706, 406, 800, 315, 0, 1115, NULL, 'Pending', '2026-10-01'),
(707, 407, 1000, 161, 15000, 16161, 'Card', 'Paid', '2026-10-05'),
(708, 408, 700, 97.5, 0, 797.5, NULL, 'Pending', '2026-10-03'),
(709, 409, 600, 18, 0, 618, 'Cash', 'Paid', '2026-10-04'),
(710, 410, 1000, 273, 3000, 4273, NULL, 'Pending', '2026-10-08'),
(711, 411, 900, 175, 0, 1075, NULL, 'Pending', '2026-10-07');

-- ===== Audit Log (12 rows - historical, before triggers exist) =====
INSERT INTO audit_log (log_id, table_name, action_type, record_id, changed_by, change_time, description) VALUES
(1, 'PATIENT', 'INSERT', 111, 'RECEPTION1', '2026-09-14 09:12:05', 'New patient registered'),
(2, 'PATIENT', 'INSERT', 112, 'RECEPTION1', '2026-09-15 10:03:41', 'New patient registered'),
(3, 'VISIT', 'INSERT', 412, 'RECEPTION1', '2026-10-05 12:20:10', 'New Appointment visit for patient 108'),
(4, 'VISIT', 'UPDATE', 412, 'RECEPTION1', '2026-10-07 16:45:02', 'Status Scheduled -> Cancelled'),
(5, 'VISIT', 'INSERT', 413, 'RECEPTION1', '2026-10-08 09:55:33', 'New Appointment visit for patient 109'),
(6, 'VISIT', 'UPDATE', 413, 'DR_RKUMAR', '2026-10-09 12:00:17', 'Status Scheduled -> Admitted'),
(7, 'VISIT', 'INSERT', 414, 'TRIAGE_NURSE', '2026-10-10 02:30:09', 'New Emergency visit for patient 110'),
(8, 'VISIT', 'UPDATE', 414, 'DR_AMENON', '2026-10-10 03:00:48', 'Status Waiting -> Admitted'),
(9, 'VISIT', 'INSERT', 415, 'TRIAGE_NURSE', '2026-10-12 20:10:21', 'New Emergency visit for patient 111'),
(10, 'VISIT', 'UPDATE', 415, 'DR_VSINGH', '2026-10-12 20:18:50', 'Status Waiting -> Under Treatment'),
(11, 'BILL', 'INSERT', 710, 'BILLING1', '2026-10-08 12:30:12', 'Bill generated: total 4273 (Pending)'),
(12, 'BILL', 'INSERT', 711, 'BILLING1', '2026-10-07 11:40:55', 'Bill generated: total 1075 (Pending)');

-- ===== Verify row counts =====
-- Expected: patient 12, doctor 10, bed 12, medicine 12, visit 20, prescription 22, bill 11, audit_log 12