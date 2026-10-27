"""
Error handling for Smart Hospital Management System.
Maps SQLite constraint/trigger errors to business rule error codes.
"""
import sqlite3
import re
from typing import Optional, Tuple


# ===== Business Rule Error Codes (from ARCHITECTURE.md §6) =====
# These mirror Oracle RAISE_APPLICATION_ERROR numbers from Review II

class BusinessRuleError(Exception):
    """Raised when a business rule is violated (or a request is invalid / not found).

    ``kind`` follows docs/API_CONTRACT.md: business_rule | not_found | validation | constraint.
    """
    kind = 'business_rule'

    def __init__(self, code: str, message: str, kind: Optional[str] = None):
        self.code = code
        self.message = message
        if kind:
            self.kind = kind
        super().__init__(f"{code}: {message}")


class ValidationError(BusinessRuleError):
    """The request itself is malformed or has an invalid value (nothing was attempted)."""
    kind = 'validation'

    def __init__(self, message: str, code: str = 'VALIDATION_ERROR'):
        super().__init__(code, message)


class NotFoundError(BusinessRuleError):
    """A referenced row does not exist."""
    kind = 'not_found'


# Error code constants
VISIT_NOT_FOUND = "VISIT_NOT_FOUND"
PATIENT_NOT_FOUND = "PATIENT_NOT_FOUND"
DOCTOR_NOT_FOUND = "DOCTOR_NOT_FOUND"
SLOT_IN_PAST = "SLOT_IN_PAST"
SLOT_TAKEN = "SLOT_TAKEN"
BAD_TRIAGE = "BAD_TRIAGE"
NO_EMERGENCY_DOCTOR = "NO_EMERGENCY_DOCTOR"
VISIT_CLOSED = "VISIT_CLOSED"
ALREADY_HAS_BED = "ALREADY_HAS_BED"
NO_FREE_BED = "NO_FREE_BED"
BED_TAKEN = "BED_TAKEN"
BAD_STATUS = "BAD_STATUS"
AUDIT_PROTECTED = "AUDIT_PROTECTED"
INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
BILL_EXISTS = "BILL_EXISTS"
NOT_DISCHARGED = "NOT_DISCHARGED"
MEDICINE_NOT_FOUND = "MEDICINE_NOT_FOUND"
BED_NOT_FOUND = "BED_NOT_FOUND"
BILL_NOT_FOUND = "BILL_NOT_FOUND"
PRESCRIPTION_NOT_FOUND = "PRESCRIPTION_NOT_FOUND"
BED_IN_USE = "BED_IN_USE"
VALIDATION_ERROR = "VALIDATION_ERROR"
FK_VIOLATION = "FK_VIOLATION"

# Constraint-related error codes (mapped from SQLite constraint names)
UQ_PATIENT_PHONE = "UQ_PATIENT_PHONE"
UQ_DOCTOR_PHONE = "UQ_DOCTOR_PHONE"
UQ_DOCTOR_SLOT = "UQ_DOCTOR_SLOT"
UQ_ACTIVE_BED = "UQ_ACTIVE_BED"
UQ_BILL_VISIT = "UQ_BILL_VISIT"

CHK_PAT_GENDER = "CHK_PAT_GENDER"
CHK_PAT_PHONE = "CHK_PAT_PHONE"
CHK_PAT_BLOOD = "CHK_PAT_BLOOD"
CHK_DOC_FEE = "CHK_DOC_FEE"
CHK_DOC_SHIFT = "CHK_DOC_SHIFT"
CHK_DOC_AVAIL = "CHK_DOC_AVAIL"
CHK_BED_WARD = "CHK_BED_WARD"
CHK_BED_STAT = "CHK_BED_STAT"
CHK_BED_CHG = "CHK_BED_CHG"
CHK_MED_PRICE = "CHK_MED_PRICE"
CHK_MED_STOCK = "CHK_MED_STOCK"
CHK_VISIT_TYPE = "CHK_VISIT_TYPE"
CHK_VISIT_STATUS = "CHK_VISIT_STATUS"
CHK_VISIT_RANGE = "CHK_VISIT_RANGE"
CHK_VISIT_TRIAGE = "CHK_VISIT_TRIAGE"
CHK_VISIT_BED = "CHK_VISIT_BED"
CHK_VISIT_DISCH = "CHK_VISIT_DISCH"
CHK_PRESC_DAYS = "CHK_PRESC_DAYS"
CHK_PRESC_QTY = "CHK_PRESC_QTY"
CHK_BILL_MODE = "CHK_BILL_MODE"
CHK_BILL_STAT = "CHK_BILL_STAT"
CHK_BILL_AMT = "CHK_BILL_AMT"
CHK_BILL_TOTAL = "CHK_BILL_TOTAL"
CHK_BILL_PAID = "CHK_BILL_PAID"
CHK_AUDIT_ACT = "CHK_AUDIT_ACT"

FK_VISIT_PATIENT = "FK_VISIT_PATIENT"
FK_VISIT_DOCTOR = "FK_VISIT_DOCTOR"
FK_VISIT_BED = "FK_VISIT_BED"
FK_PRESC_VISIT = "FK_PRESC_VISIT"
FK_PRESC_MED = "FK_PRESC_MED"
FK_BILL_VISIT = "FK_BILL_VISIT"

# Trigger error codes
TRG_REDUCE_STOCK_INSERT = "TRG_REDUCE_STOCK_INSERT"
TRG_PROTECT_AUDIT = "TRG_PROTECT_AUDIT"


# ===== Error Mapping =====

# Map SQLite constraint names to business error codes
CONSTRAINT_TO_CODE = {
    # Unique constraints
    'uq_pat_phone': UQ_PATIENT_PHONE,
    'uq_doc_phone': UQ_DOCTOR_PHONE,
    'uq_doctor_slot': UQ_DOCTOR_SLOT,
    'uq_active_bed': UQ_ACTIVE_BED,
    'uq_bill_visit': UQ_BILL_VISIT,
    
    # Check constraints
    'chk_pat_gender': CHK_PAT_GENDER,
    'chk_pat_phone': CHK_PAT_PHONE,
    'chk_pat_blood': CHK_PAT_BLOOD,
    'chk_doc_fee': CHK_DOC_FEE,
    'chk_doc_shift': CHK_DOC_SHIFT,
    'chk_doc_avail': CHK_DOC_AVAIL,
    'chk_bed_ward': CHK_BED_WARD,
    'chk_bed_stat': CHK_BED_STAT,
    'chk_bed_chg': CHK_BED_CHG,
    'chk_med_price': CHK_MED_PRICE,
    'chk_med_stock': CHK_MED_STOCK,
    'chk_visit_type': CHK_VISIT_TYPE,
    'chk_visit_status': CHK_VISIT_STATUS,
    'chk_visit_range': CHK_VISIT_RANGE,
    'chk_visit_triage': CHK_VISIT_TRIAGE,
    'chk_visit_bed': CHK_VISIT_BED,
    'chk_visit_disch': CHK_VISIT_DISCH,
    'chk_presc_days': CHK_PRESC_DAYS,
    'chk_presc_qty': CHK_PRESC_QTY,
    'chk_bill_mode': CHK_BILL_MODE,
    'chk_bill_stat': CHK_BILL_STAT,
    'chk_bill_amt': CHK_BILL_AMT,
    'chk_bill_total': CHK_BILL_TOTAL,
    'chk_bill_paid': CHK_BILL_PAID,
    'chk_audit_act': CHK_AUDIT_ACT,
    
    # Foreign keys
    'fk_visit_patient': FK_VISIT_PATIENT,
    'fk_visit_doctor': FK_VISIT_DOCTOR,
    'fk_visit_bed': FK_VISIT_BED,
    'fk_presc_visit': FK_PRESC_VISIT,
    'fk_presc_med': FK_PRESC_MED,
    'fk_bill_visit': FK_BILL_VISIT,
}

# Map trigger error messages to codes
TRIGGER_MESSAGE_TO_CODE = {
    'Insufficient stock': INSUFFICIENT_STOCK,
    'AUDIT_LOG entries cannot be modified or deleted': AUDIT_PROTECTED,
}


def map_sqlite_error(exc: sqlite3.Error) -> Tuple[str, str]:
    """
    Map a sqlite3 error to a business rule error code and message.
    
    Returns:
        Tuple of (error_code, user_friendly_message)
    """
    msg = str(exc)
    
    # Check for trigger errors first (they come as IntegrityError with custom message)
    for trigger_msg, code in TRIGGER_MESSAGE_TO_CODE.items():
        if trigger_msg in msg:
            return code, msg
    
    # Check for named CHECK constraints: "CHECK constraint failed: <name>"
    chk_match = re.search(r'CHECK constraint failed:\s*(\w+)', msg)
    if chk_match:
        constraint_name = chk_match.group(1)
        code = CONSTRAINT_TO_CODE.get(constraint_name)
        if code:
            return code, _friendly_message(code, msg)
    
    # UNIQUE: "UNIQUE constraint failed: patient.phone" or, for a multi-column index,
    # "UNIQUE constraint failed: visit.doctor_id, visit.visit_datetime"
    unique_match = re.search(r'UNIQUE constraint failed:\s*(.+)$', msg)
    if unique_match:
        cols = {c.strip() for c in unique_match.group(1).split(',')}
        if 'patient.phone' in cols:
            return UQ_PATIENT_PHONE, _friendly_message(UQ_PATIENT_PHONE, msg)
        if 'doctor.phone' in cols:
            return UQ_DOCTOR_PHONE, _friendly_message(UQ_DOCTOR_PHONE, msg)
        if {'visit.doctor_id', 'visit.visit_datetime'} <= cols:
            return UQ_DOCTOR_SLOT, _friendly_message(UQ_DOCTOR_SLOT, msg)
        if 'visit.bed_id' in cols:
            return UQ_ACTIVE_BED, _friendly_message(UQ_ACTIVE_BED, msg)
        if 'bill.visit_id' in cols:
            return UQ_BILL_VISIT, _friendly_message(UQ_BILL_VISIT, msg)
        for key, code in CONSTRAINT_TO_CODE.items():     # index name, if SQLite ever reports it
            if key.startswith('uq_') and key in msg:
                return code, _friendly_message(code, msg)

    # FOREIGN KEY: SQLite does not name the constraint, so the message stays generic
    if 'FOREIGN KEY constraint failed' in msg:
        for key, code in CONSTRAINT_TO_CODE.items():
            if key.startswith('fk_') and key in msg.lower():
                return code, _friendly_message(code, msg)
        return FK_VIOLATION, ('Blocked by a foreign key: a referenced row does not exist, '
                              'or other rows still reference this one')

    # Default
    return 'DB_ERROR', msg


def _friendly_message(code: str, raw_msg: str) -> str:
    """Generate user-friendly message for an error code."""
    messages = {
        UQ_PATIENT_PHONE: 'Phone number already registered',
        UQ_DOCTOR_PHONE: 'Doctor phone number already in use',
        UQ_DOCTOR_SLOT: 'Doctor already has an appointment at that time',
        UQ_ACTIVE_BED: 'Bed is already occupied by another admitted patient',
        UQ_BILL_VISIT: 'Bill already exists for this visit',
        
        CHK_PAT_GENDER: 'Gender must be Male, Female, or Other',
        CHK_PAT_PHONE: 'Phone number must be 10 digits',
        CHK_PAT_BLOOD: 'Invalid blood group',
        CHK_DOC_FEE: 'Consultation fee must be positive',
        CHK_DOC_SHIFT: 'Shift must be Morning, Evening, or Night',
        CHK_DOC_AVAIL: 'Availability must be Available or Busy',
        CHK_BED_WARD: 'Ward must be General, Private, ICU, or Emergency',
        CHK_BED_STAT: 'Bed status must be Free, Occupied, or Cleaning',
        CHK_BED_CHG: 'Daily charge must be positive',
        CHK_MED_PRICE: 'Medicine price must be positive',
        CHK_MED_STOCK: 'Stock quantity cannot be negative',
        CHK_VISIT_TYPE: 'Visit type must be Appointment or Emergency',
        CHK_VISIT_STATUS: 'Invalid visit status',
        CHK_VISIT_RANGE: 'Triage level must be between 1 and 4',
        CHK_VISIT_TRIAGE: 'Triage level required for Emergency visits only',
        CHK_VISIT_BED: 'Admitted visits must have a bed assigned',
        CHK_VISIT_DISCH: 'Discharge time must be after admit time',
        CHK_PRESC_DAYS: 'Duration must be positive',
        CHK_PRESC_QTY: 'Quantity must be positive',
        CHK_BILL_MODE: 'Payment mode must be Cash, Card, or UPI',
        CHK_BILL_STAT: 'Payment status must be Paid or Pending',
        CHK_BILL_AMT: 'Charges cannot be negative',
        CHK_BILL_TOTAL: 'Total amount must equal sum of charges',
        CHK_BILL_PAID: 'Paid bills must have a payment mode',
        CHK_AUDIT_ACT: 'Action type must be INSERT, UPDATE, or DELETE',
        
        FK_VISIT_PATIENT: 'Patient does not exist',
        FK_VISIT_DOCTOR: 'Doctor does not exist',
        FK_VISIT_BED: 'Bed does not exist',
        FK_PRESC_VISIT: 'Visit does not exist',
        FK_PRESC_MED: 'Medicine does not exist',
        FK_BILL_VISIT: 'Visit does not exist',
        
        INSUFFICIENT_STOCK: 'Insufficient medicine stock',
        AUDIT_PROTECTED: 'Audit log entries cannot be modified or deleted',
    }
    return messages.get(code, raw_msg)


def error_kind(code: str) -> str:
    """Contract ``error.kind`` for an error code."""
    if code.endswith('_NOT_FOUND'):
        return 'not_found'
    if code in (VALIDATION_ERROR, 'INVALID_ROLE', 'MISSING_FIELD', 'MISSING_SQL', 'BAD_REQUEST',
                'BAD_JSON', 'CSRF_REJECTED', 'SQL_NOT_ALLOWED'):
        return 'validation'
    if code in CONSTRAINT_TO_CODE.values() or code in (FK_VIOLATION, 'DB_ERROR'):
        return 'constraint'
    return 'business_rule'


def error_payload(code: str, detail: str = '', kind: Optional[str] = None) -> dict:
    """The ``error`` object of an envelope."""
    kind = kind or error_kind(code)
    return {
        'kind': kind,
        'code': code,
        'constraint': code if code in CONSTRAINT_TO_CODE.values() else None,
        'detail': detail,
    }


def make_error_envelope(code: str, message: str, detail: str = '') -> dict:
    """Create an error envelope for API responses."""
    return {
        'ok': False,
        'message': message,
        'error': error_payload(code, detail or message),
        'data': None,
        'inspector': None,
    }
