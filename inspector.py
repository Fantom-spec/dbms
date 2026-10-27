"""
Transaction Inspector.

For every state-changing API call the inspector reports what the database actually
did, so a viva audience can *see* the procedure / trigger / constraint at work.

How it works (and its honest limits)
------------------------------------
* ``Capture`` snapshots the tables before the operation, records the SQL text the
  connection executes (``sqlite3`` trace callback) and snapshots the tables again
  afterwards.  ``before`` / ``after`` therefore hold only the rows that really
  changed (matched by primary key) - they come from the database, not from the
  service layer's own bookkeeping.
* SQLite does NOT tell us which trigger ran (on this build the trace callback only
  repeats the parent statement).  ``triggers_fired`` is therefore *inferred* from
  the observed row changes using the known trigger definitions (db/triggers.sql):
  e.g. a new ``audit_log`` row with table_name 'VISIT' and action 'INSERT' can only
  have been written by ``trg_audit_visit__insert``.  Each entry carries
  ``"inferred": true`` so the UI can say so.
* The state lives on the connection (``conn.insp``), never in module globals, so
  concurrent requests cannot mix their traces.
"""
import sqlite3
import time
from typing import Any, Dict, List, Optional

TRACKED_TABLES = ['patient', 'doctor', 'bed', 'medicine', 'visit', 'prescription', 'bill', 'audit_log']
PK = {'patient': 'patient_id', 'doctor': 'doctor_id', 'bed': 'bed_id', 'medicine': 'medicine_id',
      'visit': 'visit_id', 'prescription': 'prescription_id', 'bill': 'bill_id', 'audit_log': 'log_id'}

MAX_SQL_LINES = 60
MAX_SQL_LEN = 600


def snapshot_all(conn: sqlite3.Connection) -> Dict[str, Dict[Any, Dict]]:
    """{table: {pk: row_dict}} for every tracked table."""
    snap: Dict[str, Dict[Any, Dict]] = {}
    for table in TRACKED_TABLES:
        pk = PK[table]
        snap[table] = {r[pk]: dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')}
    return snap


def diff_snapshots(before: Dict, after: Dict) -> Dict[str, Dict[str, List[Dict]]]:
    """Per table: rows before/after that were inserted, updated or deleted."""
    out: Dict[str, Dict[str, List[Dict]]] = {}
    for table in TRACKED_TABLES:
        b, a = before.get(table, {}), after.get(table, {})
        rows_b: List[Dict] = []
        rows_a: List[Dict] = []
        for pk in sorted(set(b) | set(a), key=lambda x: (str(type(x)), x)):
            if b.get(pk) != a.get(pk):
                if pk in b:
                    rows_b.append(b[pk])
                if pk in a:
                    rows_a.append(a[pk])
        if rows_b or rows_a:
            out[table] = {'before': rows_b, 'after': rows_a}
    return out


def _changes(before: Dict, after: Dict) -> Dict[str, Dict[str, List]]:
    ch: Dict[str, Dict[str, List]] = {}
    for table in TRACKED_TABLES:
        b, a = before.get(table, {}), after.get(table, {})
        ch[table] = {
            'inserted': [a[k] for k in a if k not in b],
            'deleted': [b[k] for k in b if k not in a],
            'updated': [(b[k], a[k]) for k in a if k in b and a[k] != b[k]],
        }
    return ch


def infer_triggers(before: Dict, after: Dict) -> List[Dict]:
    """Infer which physical triggers ran from the observed changes (see module doc)."""
    ch = _changes(before, after)
    fired: List[Dict] = []

    def add(name, event, effect):
        fired.append({'name': name, 'event': event, 'effect': effect, 'inferred': True})

    # trg_reduce_stock
    for row in ch['prescription']['inserted']:
        stock_after = after['medicine'].get(row['medicine_id'], {}).get('stock_quantity')
        add('trg_reduce_stock__insert', 'BEFORE INSERT ON prescription',
            f"Checked stock for medicine {row['medicine_id']} and reduced it by {row['quantity']}"
            + (f" (stock now {stock_after})" if stock_after is not None else ''))
    for row in ch['prescription']['deleted']:
        stock_after = after['medicine'].get(row['medicine_id'], {}).get('stock_quantity')
        add('trg_reduce_stock__delete', 'AFTER DELETE ON prescription',
            f"Restored {row['quantity']} unit(s) to medicine {row['medicine_id']}"
            + (f" (stock now {stock_after})" if stock_after is not None else ''))

    # audit triggers: every new audit_log row names its trigger
    for row in ch['audit_log']['inserted']:
        table = str(row['table_name']).lower()
        action = str(row['action_type']).lower()
        add(f'trg_audit_{table}__{action}', f"AFTER {row['action_type']} ON {table}",
            f"Wrote audit_log #{row['log_id']} ({row['description']}) as {row['changed_by']}")

    # trg_doctor_status
    for old, new in ch['doctor']['updated']:
        if old['availability_status'] != new['availability_status']:
            ins = any(v['doctor_id'] == new['doctor_id'] for v in ch['visit']['inserted'])
            add('trg_doctor_status__insert' if ins else 'trg_doctor_status__update',
                'AFTER INSERT ON visit' if ins else 'AFTER UPDATE OF visit_status ON visit',
                f"Doctor {new['doctor_id']} {old['availability_status']} -> {new['availability_status']}")
    return fired


class Capture:
    """Context object: take a snapshot, trace SQL, then diff.  One per operation."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.sql: List[str] = []
        self.before: Optional[Dict] = None
        self.after: Optional[Dict] = None
        self._t0 = 0.0
        self.elapsed_ms = 0.0

    def _trace(self, stmt: str) -> None:
        text = ' '.join(str(stmt).split())
        if text.startswith('-- '):          # UDF-internal statements are reported as comments
            text = text[3:]
        if len(text) > MAX_SQL_LEN:
            text = text[:MAX_SQL_LEN] + ' ...'
        if text and (not self.sql or self.sql[-1] != text):
            self.sql.append(text)

    def start(self) -> 'Capture':
        self.before = snapshot_all(self.conn)
        self._t0 = time.perf_counter()
        self.conn.set_trace_callback(self._trace)
        self.conn.insp = self
        return self

    def mark_after(self) -> None:
        """Snapshot the 'after' state now (used by sandboxes just before their ROLLBACK)."""
        self.conn.set_trace_callback(None)
        self.after = snapshot_all(self.conn)
        self.conn.set_trace_callback(self._trace)

    def finish(self) -> 'Capture':
        self.conn.set_trace_callback(None)
        self.elapsed_ms = round((time.perf_counter() - self._t0) * 1000, 2)
        # a failed operation must not leave the connection in a transaction
        if self.conn.in_transaction and self.after is None:
            try:
                self.conn.execute('ROLLBACK')
            except sqlite3.Error:
                pass
        if self.after is None:
            self.after = snapshot_all(self.conn)
        self.conn.insp = None
        if len(self.sql) > MAX_SQL_LINES:
            extra = len(self.sql) - MAX_SQL_LINES
            self.sql = self.sql[:MAX_SQL_LINES] + [f'... {extra} more statement(s)']
        return self


def build_inspector(cap: Optional[Capture], operation: str, *, component: Optional[Dict] = None,
                    functions_used: Optional[List[Dict]] = None, error: Optional[Dict] = None,
                    effect: Optional[str] = None) -> Dict:
    """Assemble the inspector object defined in ARCHITECTURE.md section 7."""
    component = component or {'name': operation, 'type': 'procedure', 'oracle_equivalent': 'N/A'}
    if cap is None or cap.before is None:
        diff, fired = {}, []
    else:
        diff = diff_snapshots(cap.before, cap.after or cap.before)
        fired = infer_triggers(cap.before, cap.after or cap.before)
    tables = [t for t in TRACKED_TABLES if t in diff]
    before = {t: diff[t]['before'] for t in tables}
    after = {t: diff[t]['after'] for t in tables}

    if error:
        result = f"Rejected - {error.get('code')}: {error.get('detail') or ''}".strip()
        eff = effect or 'Transaction rolled back; no table was changed'
    else:
        result = f'{operation} completed'
        eff = effect or ('; '.join(f"{f['name']}: {f['effect']}" for f in fired)
                         or ('changed ' + ', '.join(tables) if tables else 'read only - no table changed'))
    return {
        'operation': operation,
        'component': component,
        'tables': tables,
        'functions_used': functions_used or [],
        'triggers_fired': fired,
        'sql': cap.sql if cap else [],
        'before': before,
        'after': after,
        'viva': {
            'operation': operation,
            'tables': ', '.join(tables) if tables else 'none',
            'component': component.get('name', operation),
            'effect': eff,
            'result': result,
        },
        'elapsed_ms': cap.elapsed_ms if cap else 0,
        'notes': 'triggers_fired is inferred from the observed row changes; SQLite does not report trigger names.',
    }
