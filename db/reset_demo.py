"""Safe reset helper for the disposable SQLite demonstration database.

This module contains no interactive demo steps or web routes. It delegates to the
initializer's backup-first reset implementation.
"""
from pathlib import Path
from typing import Dict
from db.init_db import reset_in_place

def reset_demo(db_path) -> Dict:
    path = Path(db_path)
    counts = reset_in_place(path)
    return {"counts": counts, "backup": str(path) + ".pre-reset.bak"}
