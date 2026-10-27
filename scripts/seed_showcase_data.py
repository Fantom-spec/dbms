#!/usr/bin/env python3
"""Populate the Smart Hospital Management System with realistic fictional showcase records.

Run from the project root: python scripts/seed_showcase_data.py
- Uses the configured SQLite database (HOSPITAL_DB_PATH / config.DB_PATH).
- Makes a timestamped backup before modifying the database.
- Is safe to rerun: showcase patients and visits are identified by stable phone/complaint values.
- Removes only records from an earlier demo-seeding script (known demo_ accounts and
  patients with its exact synthetic phone numbers), so the UI no longer displays those labels.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from auth import create_user, init_auth_tables
from db.connection import get_connection

# Staff logins for showcasing role-based access. These are local-only sample credentials.
STAFF_USERS = [
    ("frontdesk", "Frontdesk2026", "Receptionist", "Nisha Kapoor"),
    ("triage_nurse", "TriageCare2026", "Triage Nurse", "Meera Joseph"),
    ("clinical_staff", "ClinicalCare2026", "Doctor", "Dr. Ananya Rao"),
    ("billing_staff", "BillingCare2026", "Billing", "Rohan Mehta"),
]

# Entirely fictional patient records; phone values are reserved synthetic-looking 10-digit values.
PATIENTS = [
    ("Aarav Srinivasan", "Male", "1989-04-18", "9100000101", "Adyar, Chennai", "O+", "9100000201"),
    ("Ishita Menon", "Female", "1994-09-02", "9100000102", "Velachery, Chennai", "A+", "9100000202"),
    ("Kabir Malhotra", "Male", "1978-12-11", "9100000103", "Anna Nagar, Chennai", "B+", "9100000203"),
    ("Diya Krishnan", "Female", "2001-06-24", "9100000104", "Tambaram, Chennai", "AB+", "9100000204"),
    ("Vikram Chawla", "Male", "1967-02-07", "9100000105", "T. Nagar, Chennai", "A-", "9100000205"),
    ("Ananya Bose", "Female", "1985-11-19", "9100000106", "Mylapore, Chennai", "O-", "9100000206"),
    ("Reyansh Iyer", "Male", "2012-08-30", "9100000107", "Porur, Chennai", "B-", "9100000207"),
    ("Farah Siddiqui", "Female", "1990-03-15", "9100000108", "Guindy, Chennai", "AB-", "9100000208"),
]

# complaint values are stable keys so repeat runs don't add duplicate visits.

def backup_database(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.before-showcase-{stamp}.bak")
    src = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(backup))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return backup


def remove_previous_demo_rows(conn) -> tuple[int, int]:
    """Remove only rows identifiable as belonging to the old demo script."""
    old_phones = ("9000000101", "9000000102", "9000000103", "9000000104", "9000000105")
    placeholders = ",".join("?" for _ in old_phones)
    patient_rows = conn.execute(
        f"SELECT patient_id FROM patient WHERE phone IN ({placeholders}) AND patient_name LIKE 'Demo Patient %'",
        old_phones,
    ).fetchall()
    patient_ids = [row[0] for row in patient_rows]
    removed_patients = len(patient_ids)
    removed_users = conn.execute("SELECT COUNT(*) FROM user_account WHERE username GLOB 'demo_*'").fetchone()[0]
    if patient_ids:
        marks = ",".join("?" for _ in patient_ids)
        visit_rows = conn.execute(f"SELECT visit_id FROM visit WHERE patient_id IN ({marks})", patient_ids).fetchall()
        visit_ids = [row[0] for row in visit_rows]
        if visit_ids:
            visit_marks = ",".join("?" for _ in visit_ids)
            conn.execute(f"DELETE FROM bill WHERE visit_id IN ({visit_marks})", visit_ids)
            conn.execute(f"DELETE FROM prescription WHERE visit_id IN ({visit_marks})", visit_ids)
            conn.execute(f"DELETE FROM visit WHERE visit_id IN ({visit_marks})", visit_ids)
        conn.execute(f"DELETE FROM patient WHERE patient_id IN ({marks})", patient_ids)
    conn.execute("DELETE FROM user_account WHERE username GLOB 'demo_*'")
    return removed_patients, removed_users


def main() -> int:
    db_path = Path(config.DB_PATH).resolve()
    if not db_path.exists():
        print(f"Database not found: {db_path}\nStart the app or initialize the database first.", file=sys.stderr)
        return 1
    backup = backup_database(db_path)
    conn = get_connection(str(db_path))
    try:
        init_auth_tables(conn)
        conn.execute("BEGIN")
        removed_patients, removed_users = remove_previous_demo_rows(conn)

        users_added = 0
        created_users = []
        for username, password, role, full_name in STAFF_USERS:
            if conn.execute("SELECT 1 FROM user_account WHERE username = ?", (username,)).fetchone():
                continue
            create_user(conn, username, password, role, full_name)
            users_added += 1
            created_users.append((username, password, role, full_name))

        patient_ids: dict[str, int] = {}
        patients_added = 0
        for name, gender, dob, phone, address, blood, emergency in PATIENTS:
            row = conn.execute("SELECT patient_id FROM patient WHERE phone = ?", (phone,)).fetchone()
            if row:
                patient_ids[phone] = row[0]
                continue
            cur = conn.execute(
                """INSERT INTO patient (patient_name, gender, date_of_birth, phone, address, blood_group, emergency_contact)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, gender, dob, phone, address, blood, emergency),
            )
            patient_ids[phone] = cur.lastrowid
            patients_added += 1

        # Expand pharmacy inventory only when these named items are not already present.
        # Existing medicines and their stock are preserved.
        pharmacy_items = [
            ("Oral Rehydration Salts", "MedLife Pharma", 18.00, 120),
            ("Pantoprazole 40 mg", "CureWell Labs", 6.50, 85),
            ("Ibuprofen 200 mg", "Northstar Remedies", 4.25, 95),
            ("Azithromycin 250 mg", "Asterion Pharma", 22.00, 45),
            ("Metformin 500 mg", "WellSpring Labs", 3.75, 110),
            ("Salbutamol Inhaler", "BreatheEasy Pharma", 145.00, 24),
            ("Amoxicillin 500 mg", "CureWell Labs", 12.00, 60),
            ("Cetirizine 10 mg", "Northstar Remedies", 4.00, 80),
            ("Sterile Gauze Pack", "CareFirst Supplies", 32.00, 40),
            ("Antiseptic Solution", "MedLife Pharma", 58.00, 30),
        ]
        medicines_added = 0
        for med_name, manufacturer, unit_price, stock in pharmacy_items:
            if conn.execute("SELECT 1 FROM medicine WHERE medicine_name = ?", (med_name,)).fetchone():
                continue
            next_id = conn.execute("SELECT COALESCE(MAX(medicine_id), 0) + 1 FROM medicine").fetchone()[0]
            conn.execute(
                "INSERT INTO medicine (medicine_id, medicine_name, manufacturer, price_per_unit, stock_quantity) VALUES (?, ?, ?, ?, ?)",
                (next_id, med_name, manufacturer, unit_price, stock),
            )
            medicines_added += 1

        # Add a mix of bed types/statuses without overwriting existing beds.
        beds_added = 0
        bed_specs = [
            ("General", "Free", 850.00),
            ("General", "Free", 850.00),
            ("Private", "Free", 1800.00),
            ("ICU", "Free", 3500.00),
            ("Emergency", "Free", 1200.00),
            ("General", "Cleaning", 850.00),
        ]
        for ward_type, bed_status, daily_charge in bed_specs:
            # A type/status/charge combination is enough to avoid repeated copies on reruns.
            if conn.execute(
                "SELECT 1 FROM bed WHERE ward_type = ? AND bed_status = ? AND daily_charge = ? LIMIT 1",
                (ward_type, bed_status, daily_charge),
            ).fetchone():
                continue
            next_bed_id = conn.execute("SELECT COALESCE(MAX(bed_id), 0) + 1 FROM bed").fetchone()[0]
            conn.execute(
                "INSERT INTO bed (bed_id, ward_type, bed_status, daily_charge) VALUES (?, ?, ?, ?)",
                (next_bed_id, ward_type, bed_status, daily_charge),
            )
            beds_added += 1

        doctors = {row["doctor_id"]: row for row in conn.execute("SELECT * FROM doctor ORDER BY doctor_id").fetchall()}
        if not doctors:
            raise RuntimeError("No doctors found. Seed the hospital database before running this script.")

        now = datetime.now().replace(second=0, microsecond=0)
        # 8 records across appointment, emergency, treatment, admission, discharge and cancellation views.
        specs = [
            # phone, doctor_id, type, offset, complaint, triage, status, bed_id, admit_offset_hours, discharge_offset_hours
            ("9100000101", 202, "Appointment", 1, "Annual wellness consultation", None, "Scheduled", None, None, None),
            ("9100000102", 201, "Appointment", 2, "Cardiology follow-up and ECG review", None, "Scheduled", None, None, None),
            ("9100000103", 203, "Emergency", 0, "Acute chest discomfort and dizziness", 1, "Waiting", None, None, None),
            ("9100000104", 206, "Emergency", 0, "High fever with dehydration", 2, "Under Treatment", None, None, None),
            ("9100000105", 205, "Emergency", 0, "Severe headache requiring observation", 2, "Admitted", None, -3, None),
            ("9100000106", 204, "Appointment", -3, "Knee pain follow-up", None, "Discharged", None, -70, -26),
            ("9100000107", 206, "Appointment", 3, "Paediatric wellness review", None, "Scheduled", None, None, None),
            ("9100000108", 210, "Appointment", -1, "Dermatology review", None, "Cancelled", None, None, None),
        ]
        visits_added = prescriptions_added = bills_added = 0
        visit_ids: dict[str, int] = {}
        for phone, doctor_id, visit_type, day_offset, complaint, triage, status, _bed_unused, admit_hours, discharge_hours in specs:
            patient_id = patient_ids[phone]
            existing = conn.execute(
                "SELECT * FROM visit WHERE patient_id = ? AND complaint = ? ORDER BY visit_id LIMIT 1",
                (patient_id, complaint),
            ).fetchone()
            if existing:
                visit_ids[complaint] = existing["visit_id"]
                continue
            if status == "Admitted":
                visit_dt = now - timedelta(hours=4)
            elif status == "Under Treatment":
                visit_dt = now - timedelta(minutes=45)
            elif status == "Waiting":
                visit_dt = now - timedelta(minutes=15)
            else:
                visit_dt = now + timedelta(days=day_offset)
            visit_time = visit_dt.strftime("%Y-%m-%d %H:%M:%S")
            bed_id = None
            admit_time = (now + timedelta(hours=admit_hours)).strftime("%Y-%m-%d %H:%M:%S") if admit_hours is not None else None
            discharge_time = (now + timedelta(hours=discharge_hours)).strftime("%Y-%m-%d %H:%M:%S") if discharge_hours is not None else None
            if status == "Admitted":
                free_bed = conn.execute("SELECT bed_id FROM bed WHERE bed_status = 'Free' AND ward_type IN ('ICU','Private','General') ORDER BY CASE ward_type WHEN 'ICU' THEN 1 WHEN 'Private' THEN 2 ELSE 3 END, bed_id LIMIT 1").fetchone()
                if not free_bed:
                    raise RuntimeError("No free bed available for the showcase admission.")
                bed_id = free_bed["bed_id"]
            cur = conn.execute(
                """INSERT INTO visit (patient_id, doctor_id, bed_id, visit_type, visit_datetime, complaint,
                       triage_level, visit_status, admit_time, discharge_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (patient_id, doctor_id, bed_id, visit_type, visit_time, complaint, triage, status, admit_time, discharge_time),
            )
            visit_id = cur.lastrowid
            visit_ids[complaint] = visit_id
            visits_added += 1
            if status == "Admitted":
                conn.execute("UPDATE bed SET bed_status = 'Occupied' WHERE bed_id = ?", (bed_id,))

        # Add believable prescription lines to active and discharged visits. The stock trigger
        # reduces inventory automatically when installed; quantities are intentionally modest.
        prescription_specs = [
            ("Acute chest discomfort and dizziness", 506, "1-0-0", 14, 14),
            ("High fever with dehydration", 501, "1-1-1", 3, 9),
            ("High fever with dehydration", 512, "As directed", 2, 4),
            ("Severe headache requiring observation", 505, "1-0-0", 5, 5),
            ("Knee pain follow-up", 504, "1-0-1", 5, 10),
            ("Knee pain follow-up", 511, "0-1-0", 14, 14),
            ("Paediatric wellness review", 503, "0-0-1", 3, 3),
        ]
        for complaint, medicine_id, dosage, days, quantity in prescription_specs:
            visit_id = visit_ids.get(complaint)
            if visit_id is None:
                continue
            if conn.execute("SELECT 1 FROM prescription WHERE visit_id = ? AND medicine_id = ?", (visit_id, medicine_id)).fetchone():
                continue
            med = conn.execute("SELECT price_per_unit, stock_quantity FROM medicine WHERE medicine_id = ?", (medicine_id,)).fetchone()
            if not med or med["stock_quantity"] < quantity:
                continue
            conn.execute(
                "INSERT INTO prescription (visit_id, medicine_id, dosage, duration_days, quantity) VALUES (?, ?, ?, ?, ?)",
                (visit_id, medicine_id, dosage, days, quantity),
            )
            prescriptions_added += 1

        # Generate bills for visits that have enough clinical data to demonstrate billing.
        bill_specs = [
            ("Knee pain follow-up", "UPI", "Paid", 0),
            ("High fever with dehydration", None, "Pending", 0),
            ("Severe headache requiring observation", None, "Pending", 1),
            ("Acute chest discomfort and dizziness", None, "Pending", 0),
            ("Annual wellness consultation", "Card", "Paid", 0),
            ("Cardiology follow-up and ECG review", "Cash", "Paid", 0),
            ("Paediatric wellness review", None, "Pending", 0),
        ]
        for complaint, payment_mode, payment_status, bed_days in bill_specs:
            visit_id = visit_ids.get(complaint)
            if visit_id is None or conn.execute("SELECT 1 FROM bill WHERE visit_id = ?", (visit_id,)).fetchone():
                continue
            visit = conn.execute("SELECT doctor_id, bed_id FROM visit WHERE visit_id = ?", (visit_id,)).fetchone()
            doctor = conn.execute("SELECT consultation_fee FROM doctor WHERE doctor_id = ?", (visit["doctor_id"],)).fetchone()
            medicine_charge = conn.execute(
                "SELECT COALESCE(SUM(p.quantity * m.price_per_unit), 0) FROM prescription p JOIN medicine m ON m.medicine_id = p.medicine_id WHERE p.visit_id = ?",
                (visit_id,),
            ).fetchone()[0]
            bed_charge = 0.0
            if visit["bed_id"] is not None and bed_days:
                bed_charge = conn.execute("SELECT daily_charge FROM bed WHERE bed_id = ?", (visit["bed_id"],)).fetchone()[0] * bed_days
            consultation_charge = float(doctor["consultation_fee"])
            total = round(consultation_charge + float(medicine_charge) + float(bed_charge), 2)
            conn.execute(
                """INSERT INTO bill (visit_id, consultation_charge, medicine_charge, bed_charge, total_amount,
                       payment_mode, payment_status, bill_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (visit_id, consultation_charge, round(float(medicine_charge), 2), round(float(bed_charge), 2), total,
                 payment_mode, payment_status, now.strftime("%Y-%m-%d")),
            )
            bills_added += 1

        conn.commit()
        counts = {}
        for table in ("patient", "doctor", "visit", "prescription", "bed", "medicine", "bill", "audit_log", "user_account"):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("\nHospital showcase records are ready.")
    print(f"Database: {db_path}")
    print(f"Backup:   {backup}")
    print(f"Removed previous placeholder rows: {removed_patients} patients, {removed_users} old accounts")
    print(f"Added: {users_added} staff accounts, {patients_added} patients, {visits_added} visits, {prescriptions_added} prescription lines, {bills_added} bills, {medicines_added} pharmacy items, {beds_added} beds")
    print("\nNew staff credentials:")
    if created_users:
        for username, password, role, full_name in created_users:
            print(f"  {role:14} {username:16} / {password}  ({full_name})")
    else:
        print("  No new staff accounts were needed; existing passwords were left unchanged.")
    print("\nCurrent table totals:")
    for table, count in counts.items():
        print(f"  {table:14} {count}")
    print("\nAll patient and clinical records are fictional and intended only for local project showcasing.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Showcase seeding failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
