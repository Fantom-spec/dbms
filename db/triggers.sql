-- Smart Hospital Management System - SQLite Triggers
-- 6 logical triggers = 15 physical triggers (SQLite is single-event)
-- Run AFTER seed.sql so seed doesn't generate extra audit rows or reduce stock
-- Naming: trg_<logical>__<event>

-- ===== trg_reduce_stock (2 triggers) =====
-- BEFORE INSERT on prescription: check stock, reduce if sufficient
CREATE TRIGGER trg_reduce_stock__insert
BEFORE INSERT ON prescription
BEGIN
    SELECT RAISE(ABORT, 'Insufficient stock for ' || m.medicine_name ||
           ': available ' || m.stock_quantity || ', requested ' || NEW.quantity)
    FROM medicine m
    WHERE m.medicine_id = NEW.medicine_id
      AND m.stock_quantity < NEW.quantity;

    UPDATE medicine
    SET stock_quantity = stock_quantity - NEW.quantity
    WHERE medicine_id = NEW.medicine_id;
END;

-- AFTER DELETE on prescription: restore stock
CREATE TRIGGER trg_reduce_stock__delete
AFTER DELETE ON prescription
BEGIN
    UPDATE medicine
    SET stock_quantity = stock_quantity + OLD.quantity
    WHERE medicine_id = OLD.medicine_id;
END;

-- ===== trg_audit_visit (3 triggers) =====
-- AFTER INSERT on visit
CREATE TRIGGER trg_audit_visit__insert
AFTER INSERT ON visit
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('VISIT', 'INSERT', NEW.visit_id,
            (SELECT username FROM app_session WHERE id = 1),
            'New ' || NEW.visit_type || ' visit for patient ' || NEW.patient_id);
END;

-- AFTER UPDATE on visit
CREATE TRIGGER trg_audit_visit__update
AFTER UPDATE ON visit
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('VISIT', 'UPDATE', NEW.visit_id,
            (SELECT username FROM app_session WHERE id = 1),
            'Status ' || OLD.visit_status || ' -> ' || NEW.visit_status);
END;

-- AFTER DELETE on visit
CREATE TRIGGER trg_audit_visit__delete
AFTER DELETE ON visit
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('VISIT', 'DELETE', OLD.visit_id,
            (SELECT username FROM app_session WHERE id = 1),
            'Visit deleted (patient ' || OLD.patient_id || ')');
END;

-- ===== trg_audit_bill (3 triggers) =====
-- AFTER INSERT on bill
CREATE TRIGGER trg_audit_bill__insert
AFTER INSERT ON bill
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('BILL', 'INSERT', NEW.bill_id,
            (SELECT username FROM app_session WHERE id = 1),
            'Bill generated: total ' || NEW.total_amount || ' (' || NEW.payment_status || ')');
END;

-- AFTER UPDATE on bill
CREATE TRIGGER trg_audit_bill__update
AFTER UPDATE ON bill
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('BILL', 'UPDATE', NEW.bill_id,
            (SELECT username FROM app_session WHERE id = 1),
            'Payment status ' || OLD.payment_status || ' -> ' || NEW.payment_status);
END;

-- AFTER DELETE on bill
CREATE TRIGGER trg_audit_bill__delete
AFTER DELETE ON bill
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('BILL', 'DELETE', OLD.bill_id,
            (SELECT username FROM app_session WHERE id = 1),
            'Bill deleted');
END;

-- ===== trg_audit_patient (3 triggers) =====
-- AFTER INSERT on patient
CREATE TRIGGER trg_audit_patient__insert
AFTER INSERT ON patient
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('PATIENT', 'INSERT', NEW.patient_id,
            (SELECT username FROM app_session WHERE id = 1),
            'New patient registered');
END;

-- AFTER UPDATE on patient
CREATE TRIGGER trg_audit_patient__update
AFTER UPDATE ON patient
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('PATIENT', 'UPDATE', NEW.patient_id,
            (SELECT username FROM app_session WHERE id = 1),
            'Patient details updated');
END;

-- AFTER DELETE on patient
CREATE TRIGGER trg_audit_patient__delete
AFTER DELETE ON patient
BEGIN
    INSERT INTO audit_log (table_name, action_type, record_id, changed_by, description)
    VALUES ('PATIENT', 'DELETE', OLD.patient_id,
            (SELECT username FROM app_session WHERE id = 1),
            'Patient record deleted');
END;

-- ===== trg_doctor_status (2 triggers) =====
-- AFTER INSERT on visit (when visit inserted as Under Treatment)
CREATE TRIGGER trg_doctor_status__insert
AFTER INSERT ON visit
WHEN NEW.visit_status = 'Under Treatment'
BEGIN
    UPDATE doctor
    SET availability_status = 'Busy'
    WHERE doctor_id = NEW.doctor_id;
END;

-- AFTER UPDATE OF visit_status on visit
CREATE TRIGGER trg_doctor_status__update
AFTER UPDATE OF visit_status ON visit
WHEN NEW.visit_status = 'Under Treatment' OR OLD.visit_status = 'Under Treatment'
BEGIN
    -- Visit becomes Under Treatment -> doctor Busy
    UPDATE doctor
    SET availability_status = 'Busy'
    WHERE doctor_id = NEW.doctor_id
      AND NEW.visit_status = 'Under Treatment';

    -- Visit leaves Under Treatment -> doctor Available
    UPDATE doctor
    SET availability_status = 'Available'
    WHERE doctor_id = NEW.doctor_id
      AND OLD.visit_status = 'Under Treatment'
      AND NEW.visit_status <> 'Under Treatment';
END;

-- ===== trg_protect_audit (2 triggers) =====
-- BEFORE UPDATE on audit_log
CREATE TRIGGER trg_protect_audit__update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'AUDIT_LOG entries cannot be modified or deleted');
END;

-- BEFORE DELETE on audit_log
CREATE TRIGGER trg_protect_audit__delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'AUDIT_LOG entries cannot be modified or deleted');
END;