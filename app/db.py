import sqlite3
from contextlib import contextmanager

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL UNIQUE,
    uploaded_at TEXT NOT NULL,
    invoice_type_name TEXT,
    invoice_form_number TEXT,
    invoice_number TEXT,
    invoice_date TEXT,
    seller_name TEXT,
    seller_tax_code TEXT,
    buyer_name TEXT,
    buyer_tax_code TEXT,
    buyer_company_name TEXT,
    buyer_address TEXT,
    buyer_bank_account TEXT,
    buyer_payment_method TEXT,
    subtotal REAL,
    tax_amount REAL,
    total_amount REAL,
    currency TEXT DEFAULT 'VND',
    status TEXT NOT NULL DEFAULT 'pending_review',
    review_reasons TEXT,
    ocr_raw_json TEXT,
    ocr_provider TEXT,
    total_mismatch INTEGER NOT NULL DEFAULT 0,
    duplicate_flag INTEGER NOT NULL DEFAULT 0,
    duplicate_of_invoice_id INTEGER,
    confirmed_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    description TEXT,
    quantity REAL,
    unit_price REAL,
    line_total REAL
);

CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_seller_number ON invoices(seller_tax_code, invoice_number);
"""


def init_db() -> None:
    settings.db_path_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        _migrate_add_missing_columns(conn)


_NEW_COLUMNS = [
    "invoice_type_name",
    "invoice_form_number",
    "buyer_company_name",
    "buyer_address",
    "buyer_bank_account",
    "buyer_payment_method",
]


def _migrate_add_missing_columns(conn: sqlite3.Connection) -> None:
    """Them cot moi vao bang da ton tai tu ban cai dat truoc (SQLite khong
    ho tro 'ADD COLUMN IF NOT EXISTS' o moi phien ban, nen tu kiem tra)."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(invoices)")}
    for column in _NEW_COLUMNS:
        if column not in existing:
            conn.execute(f"ALTER TABLE invoices ADD COLUMN {column} TEXT")


@contextmanager
def get_connection():
    conn = sqlite3.connect(settings.db_path_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
