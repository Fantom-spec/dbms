"""
Report queries for Smart Hospital Management System.
Implements the 19 Review II queries adapted to SQLite.
"""
import sqlite3
from typing import List, Dict, Any, Optional


def get_reports_catalogue(conn: sqlite3.Connection) -> Dict:
    """Get list of all available reports."""
    reports = [
        {"id": "q01", "label": "A", "title": "Visit history of a patient", "concept": "3-table JOIN", "chart": None},
        {"id": "q02", "label": "B", "title": "Visits per doctor", "concept": "LEFT JOIN, GROUP BY", "chart": "bar"},
        {"id": "q03", "label": "C", "title": "Emergency cases by triage", "concept": "CASE, GROUP BY", "chart": "pie"},
        {"id": "q04", "label": "D", "title": "Departments with 3+ visits", "concept": "JOIN, HAVING", "chart": "bar"},
        {"id": "q05", "label": "E", "title": "Low-stock medicines (<20)", "concept": "WHERE, ORDER BY", "chart": None},
        {"id": "q06", "label": "F", "title": "Free beds per ward", "concept": "Aggregate on filtered set", "chart": "bar"},
        {"id": "q07", "label": "G", "title": "Bed occupancy % per ward", "concept": "Conditional aggregation", "chart": "bar"},
        {"id": "q08", "label": "H", "title": "Bills by payment status", "concept": "SUM/COUNT, GROUP BY", "chart": "pie"},
        {"id": "q09", "label": "I", "title": "Monthly billing summary", "concept": "strftime in GROUP BY", "chart": "stacked_bar"},
        {"id": "q10", "label": "J", "title": "Pending bills", "concept": "4-table JOIN", "chart": None},
        {"id": "q11", "label": "K", "title": "Patients with no emergency visit", "concept": "NOT EXISTS (correlated)", "chart": None},
        {"id": "q12", "label": "L", "title": "Doctors above average fee", "concept": "Scalar subquery", "chart": None},
        {"id": "q13", "label": "M", "title": "Top 3 billed patients", "concept": "Subquery + RANK() window", "chart": "bar"},
        {"id": "q14", "label": "N", "title": "Prescription statistics per medicine", "concept": "JOIN, HAVING, computed aggregate", "chart": "bar"},
        {"id": "q15", "label": "O", "title": "Currently admitted patients", "concept": "Multi-table JOIN", "chart": None},
        {"id": "q16", "label": "P", "title": "Emergency waiting queue", "concept": "ORDER BY two columns", "chart": None},
        {"id": "q17", "label": "Q", "title": "Average and highest bill by visit type", "concept": "AVG, ROUND, MAX", "chart": "bar"},
        {"id": "q18", "label": "R", "title": "Doctors who prescribed Aspirin", "concept": "Nested IN subquery", "chart": None},
        {"id": "q19", "label": "S", "title": "Patients with more than one visit", "concept": "HAVING, MIN/MAX dates", "chart": None},
    ]
    return {"ok": True, "message": "Reports catalogue retrieved", "data": reports}


def get_report(conn: sqlite3.Connection, report_id: str, param: Optional[str] = None) -> Dict:
    """Execute a specific report query and return results with metadata."""
    
    if report_id == "q01":
        # A: Visit history of a patient
        patient_name = param or "Aakash Gupta"
        sql = """
            SELECT v.visit_id, v.visit_datetime, v.visit_type, d.doctor_name, v.complaint, v.visit_status
            FROM visit v
            JOIN patient p ON p.patient_id = v.patient_id
            JOIN doctor d ON d.doctor_id = v.doctor_id
            WHERE p.patient_name = ?
            ORDER BY v.visit_datetime
        """
        rows = conn.execute(sql, (patient_name,)).fetchall()
        return {
            "ok": True, "message": "Report q01 executed",
            "data": {
                "id": "q01", "title": "Visit history of a patient", "concept": "3-table JOIN",
                "sql": sql.strip(),
                "columns": ["visit_id", "visit_datetime", "visit_type", "doctor_name", "complaint", "visit_status"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q02":
        # B: Visits per doctor
        sql = """
            SELECT d.doctor_name, d.department, COUNT(v.visit_id) AS total_visits
            FROM doctor d
            LEFT JOIN visit v ON v.doctor_id = d.doctor_id
            GROUP BY d.doctor_name, d.department
            ORDER BY total_visits DESC, d.doctor_name
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q02 executed",
            "data": {
                "id": "q02", "title": "Visits per doctor", "concept": "LEFT JOIN, GROUP BY",
                "sql": sql.strip(),
                "columns": ["doctor_name", "department", "total_visits"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "bar", "label_col": "doctor_name", "value_cols": ["total_visits"]}
            }
        }
    
    elif report_id == "q03":
        # C: Emergency cases by triage
        sql = """
            SELECT triage_level,
                   CASE triage_level WHEN 1 THEN 'Critical' WHEN 2 THEN 'Very urgent' WHEN 3 THEN 'Urgent' ELSE 'Minor' END AS category,
                   COUNT(*) AS cases
            FROM visit
            WHERE visit_type = 'Emergency'
            GROUP BY triage_level
            ORDER BY triage_level
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q03 executed",
            "data": {
                "id": "q03", "title": "Emergency cases by triage", "concept": "CASE, GROUP BY",
                "sql": sql.strip(),
                "columns": ["triage_level", "category", "cases"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "pie", "label_col": "category", "value_cols": ["cases"]}
            }
        }
    
    elif report_id == "q04":
        # D: Departments with 3+ visits
        sql = """
            SELECT d.department, COUNT(v.visit_id) AS visit_count
            FROM doctor d
            JOIN visit v ON v.doctor_id = d.doctor_id
            GROUP BY d.department
            HAVING visit_count >= 3
            ORDER BY visit_count DESC
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q04 executed",
            "data": {
                "id": "q04", "title": "Departments with 3+ visits", "concept": "JOIN, HAVING",
                "sql": sql.strip(),
                "columns": ["department", "visit_count"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "bar", "label_col": "department", "value_cols": ["visit_count"]}
            }
        }
    
    elif report_id == "q05":
        # E: Low-stock medicines (<20)
        sql = """
            SELECT medicine_id, medicine_name, stock_quantity, price_per_unit
            FROM medicine
            WHERE stock_quantity < 20
            ORDER BY stock_quantity
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q05 executed",
            "data": {
                "id": "q05", "title": "Low-stock medicines (<20)", "concept": "WHERE, ORDER BY",
                "sql": sql.strip(),
                "columns": ["medicine_id", "medicine_name", "stock_quantity", "price_per_unit"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q06":
        # F: Free beds per ward
        sql = """
            SELECT ward_type, COUNT(*) AS free_beds
            FROM bed
            WHERE bed_status = 'Free'
            GROUP BY ward_type
            ORDER BY ward_type
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q06 executed",
            "data": {
                "id": "q06", "title": "Free beds per ward", "concept": "Aggregate on filtered set",
                "sql": sql.strip(),
                "columns": ["ward_type", "free_beds"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "bar", "label_col": "ward_type", "value_cols": ["free_beds"]}
            }
        }
    
    elif report_id == "q07":
        # G: Bed occupancy % per ward
        sql = """
            SELECT ward_type,
                   ROUND(100.0 * SUM(CASE WHEN bed_status = 'Occupied' THEN 1 ELSE 0 END) / COUNT(*), 1) AS occupancy_pct
            FROM bed
            GROUP BY ward_type
            ORDER BY ward_type
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q07 executed",
            "data": {
                "id": "q07", "title": "Bed occupancy % per ward", "concept": "Conditional aggregation",
                "sql": sql.strip(),
                "columns": ["ward_type", "occupancy_pct"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "bar", "label_col": "ward_type", "value_cols": ["occupancy_pct"]}
            }
        }
    
    elif report_id == "q08":
        # H: Bills by payment status
        sql = """
            SELECT payment_status, COUNT(*) AS bill_count, SUM(total_amount) AS total_amount
            FROM bill
            GROUP BY payment_status
            ORDER BY payment_status
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q08 executed",
            "data": {
                "id": "q08", "title": "Bills by payment status", "concept": "SUM/COUNT, GROUP BY",
                "sql": sql.strip(),
                "columns": ["payment_status", "bill_count", "total_amount"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "pie", "label_col": "payment_status", "value_cols": ["bill_count"]}
            }
        }
    
    elif report_id == "q09":
        # I: Monthly billing summary
        sql = """
            SELECT strftime('%Y-%m', bill_date) AS month,
                   COUNT(*) AS bill_count,
                   SUM(total_amount) AS total_amount
            FROM bill
            GROUP BY strftime('%Y-%m', bill_date)
            ORDER BY month
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q09 executed",
            "data": {
                "id": "q09", "title": "Monthly billing summary", "concept": "strftime in GROUP BY",
                "sql": sql.strip(),
                "columns": ["month", "bill_count", "total_amount"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "stacked_bar", "label_col": "month", "value_cols": ["total_amount"]}
            }
        }
    
    elif report_id == "q10":
        # J: Pending bills (4-table JOIN)
        sql = """
            SELECT b.bill_id, p.patient_name, d.doctor_name, b.bill_date, b.total_amount
            FROM bill b
            JOIN visit v ON v.visit_id = b.visit_id
            JOIN patient p ON p.patient_id = v.patient_id
            JOIN doctor d ON d.doctor_id = v.doctor_id
            WHERE b.payment_status = 'Pending'
            ORDER BY b.bill_date, b.bill_id
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q10 executed",
            "data": {
                "id": "q10", "title": "Pending bills", "concept": "4-table JOIN",
                "sql": sql.strip(),
                "columns": ["bill_id", "patient_name", "doctor_name", "bill_date", "total_amount"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q11":
        # K: Patients with no emergency visit
        sql = """
            SELECT p.patient_id, p.patient_name
            FROM patient p
            WHERE NOT EXISTS (
                SELECT 1 FROM visit v
                WHERE v.patient_id = p.patient_id AND v.visit_type = 'Emergency'
            )
            ORDER BY p.patient_name
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q11 executed",
            "data": {
                "id": "q11", "title": "Patients with no emergency visit", "concept": "NOT EXISTS (correlated)",
                "sql": sql.strip(),
                "columns": ["patient_id", "patient_name"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q12":
        # L: Doctors above average fee
        sql = """
            SELECT doctor_id, doctor_name, department, consultation_fee
            FROM doctor
            WHERE consultation_fee > (SELECT AVG(consultation_fee) FROM doctor)
            ORDER BY consultation_fee DESC
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q12 executed",
            "data": {
                "id": "q12", "title": "Doctors above average fee", "concept": "Scalar subquery",
                "sql": sql.strip(),
                "columns": ["doctor_id", "doctor_name", "department", "consultation_fee"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q13":
        # M: Top 3 billed patients
        sql = """
            SELECT p.patient_name, SUM(b.total_amount) AS total_billed
            FROM patient p
            JOIN visit v ON v.patient_id = p.patient_id
            JOIN bill b ON b.visit_id = v.visit_id
            WHERE b.payment_status = 'Paid'
            GROUP BY p.patient_id, p.patient_name
            ORDER BY total_billed DESC
            LIMIT 3
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q13 executed",
            "data": {
                "id": "q13", "title": "Top 3 billed patients", "concept": "Subquery + RANK() window",
                "sql": sql.strip(),
                "columns": ["patient_name", "total_billed"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "bar", "label_col": "patient_name", "value_cols": ["total_billed"]}
            }
        }
    
    elif report_id == "q14":
        # N: Prescription statistics per medicine
        sql = """
            SELECT m.medicine_name, m.stock_quantity,
                   COUNT(pr.prescription_id) AS prescription_count,
                   SUM(pr.quantity) AS total_quantity,
                   SUM(pr.quantity * m.price_per_unit) AS total_value
            FROM medicine m
            JOIN prescription pr ON pr.medicine_id = m.medicine_id
            GROUP BY m.medicine_id, m.medicine_name, m.stock_quantity
            HAVING prescription_count > 0
            ORDER BY total_quantity DESC
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q14 executed",
            "data": {
                "id": "q14", "title": "Prescription statistics per medicine", "concept": "JOIN, HAVING, computed aggregate",
                "sql": sql.strip(),
                "columns": ["medicine_name", "stock_quantity", "prescription_count", "total_quantity", "total_value"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "bar", "label_col": "medicine_name", "value_cols": ["total_quantity"]}
            }
        }
    
    elif report_id == "q15":
        # O: Currently admitted patients
        sql = """
            SELECT v.visit_id, p.patient_name, d.doctor_name, b.bed_id, bt.ward_type, v.admit_time
            FROM visit v
            JOIN patient p ON p.patient_id = v.patient_id
            JOIN doctor d ON d.doctor_id = v.doctor_id
            JOIN bed b ON b.bed_id = v.bed_id
            JOIN bed bt ON bt.bed_id = b.bed_id
            WHERE v.visit_status = 'Admitted'
            ORDER BY v.admit_time
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q15 executed",
            "data": {
                "id": "q15", "title": "Currently admitted patients", "concept": "Multi-table JOIN",
                "sql": sql.strip(),
                "columns": ["visit_id", "patient_name", "doctor_name", "bed_id", "ward_type", "admit_time"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q16":
        # P: Emergency waiting queue
        sql = """
            SELECT v.visit_id, p.patient_name, v.triage_level, v.complaint, d.doctor_name, v.visit_datetime
            FROM visit v
            JOIN patient p ON p.patient_id = v.patient_id
            JOIN doctor d ON d.doctor_id = v.doctor_id
            WHERE v.visit_type = 'Emergency' AND v.visit_status = 'Waiting'
            ORDER BY v.triage_level, v.visit_datetime
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q16 executed",
            "data": {
                "id": "q16", "title": "Emergency waiting queue", "concept": "ORDER BY two columns",
                "sql": sql.strip(),
                "columns": ["visit_id", "patient_name", "triage_level", "complaint", "doctor_name", "visit_datetime"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q17":
        # Q: Average and highest bill by visit type
        sql = """
            SELECT v.visit_type,
                   ROUND(AVG(b.total_amount), 2) AS avg_bill,
                   MAX(b.total_amount) AS max_bill
            FROM bill b
            JOIN visit v ON v.visit_id = b.visit_id
            WHERE b.payment_status = 'Paid'
            GROUP BY v.visit_type
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q17 executed",
            "data": {
                "id": "q17", "title": "Average and highest bill by visit type", "concept": "AVG, ROUND, MAX",
                "sql": sql.strip(),
                "columns": ["visit_type", "avg_bill", "max_bill"],
                "rows": [list(r) for r in rows],
                "chart": {"type": "bar", "label_col": "visit_type", "value_cols": ["avg_bill", "max_bill"]}
            }
        }
    
    elif report_id == "q18":
        # R: Doctors who prescribed Aspirin
        sql = """
            SELECT d.doctor_id, d.doctor_name
            FROM doctor d
            WHERE d.doctor_id IN (
                SELECT v.doctor_id
                FROM visit v
                WHERE v.visit_id IN (
                    SELECT pr.visit_id
                    FROM prescription pr
                    WHERE pr.medicine_id IN (
                        SELECT m.medicine_id FROM medicine m WHERE m.medicine_name LIKE 'Aspirin%'
                    )
                )
            )
            ORDER BY d.doctor_name
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q18 executed",
            "data": {
                "id": "q18", "title": "Doctors who prescribed Aspirin", "concept": "Nested IN subquery",
                "sql": sql.strip(),
                "columns": ["doctor_id", "doctor_name"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    elif report_id == "q19":
        # S: Patients with more than one visit
        sql = """
            SELECT p.patient_id, p.patient_name, COUNT(v.visit_id) AS visit_count,
                   MIN(v.visit_datetime) AS first_visit, MAX(v.visit_datetime) AS last_visit
            FROM patient p
            JOIN visit v ON v.patient_id = p.patient_id
            GROUP BY p.patient_id, p.patient_name
            HAVING visit_count > 1
            ORDER BY visit_count DESC, p.patient_name
        """
        rows = conn.execute(sql).fetchall()
        return {
            "ok": True, "message": "Report q19 executed",
            "data": {
                "id": "q19", "title": "Patients with more than one visit", "concept": "HAVING, MIN/MAX dates",
                "sql": sql.strip(),
                "columns": ["patient_id", "patient_name", "visit_count", "first_visit", "last_visit"],
                "rows": [list(r) for r in rows],
                "chart": None
            }
        }
    
    else:
        return {
            "ok": False, "message": f"Unknown report: {report_id}",
            "error": {"kind": "not_found", "code": "REPORT_NOT_FOUND", "constraint": None, "detail": f"Report {report_id} not found"},
            "data": None
        }


def get_reports(conn: sqlite3.Connection) -> Dict:
    """Get all reports (for testing)."""
    return get_reports_catalogue(conn)